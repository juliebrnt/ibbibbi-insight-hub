"""Read any uploaded file into one or more raw tables of strings.

Nothing here knows about business meaning. It only turns bytes into tidy tables:
detects encoding and delimiter, finds the real header row, unpacks ZIPs, reads
every sheet, flattens JSON and splits pasted text into feedback items.
"""
from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
from charset_normalizer import from_bytes


@dataclass
class RawTable:
    name: str  # file name (plus sheet)
    df: pd.DataFrame
    file_name: str
    sheet: str | None = None
    kind_hint: str | None = None  # e.g. 'text' for pasted messages
    notes: list[str] = field(default_factory=list)


class ReadError(Exception):
    """A friendly, user-facing explanation of why a file could not be read."""


TEXT_EXT = {".txt", ".md", ".markdown"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".heic", ".gif"}


def decode(data: bytes) -> str:
    if data.startswith(b"\xef\xbb\xbf"):
        return data[3:].decode("utf-8")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        best = from_bytes(data[:200_000]).best()
        enc = best.encoding if best else "latin-1"
        return data.decode(enc, errors="replace")


def _sniff_delimiter(text: str) -> str:
    sample = "\n".join([ln for ln in text.splitlines()[:60] if ln.strip() and not ln.startswith("#")][:40])
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        counts = {d: sample.count(d) for d in (",", ";", "\t", "|")}
        return max(counts, key=counts.get)


def find_header_row(grid: list[list[str]]) -> int:
    """Pick the first row that looks like a header: many non-empty, mostly non-numeric cells,
    followed by rows of similar width. Skips titles, comment lines and blank rows."""
    best, best_score = 0, -1.0
    widths = [sum(1 for c in r if str(c).strip()) for r in grid[:60]]
    max_w = max(widths) if widths else 0
    for i, row in enumerate(grid[:40]):
        cells = [str(c).strip() for c in row]
        filled = [c for c in cells if c]
        if not filled or (filled[0].startswith("#")):
            continue
        textish = sum(1 for c in filled if not re.fullmatch(r"[\d.,\-/: %€$]+", c)) / len(filled)
        below = widths[i + 1:i + 6]
        consistency = (sum(1 for w in below if w >= 0.6 * len(filled)) / len(below)) if below else 0
        score = (len(filled) / max(max_w, 1)) * 2 + textish * 1.5 + consistency
        if len(filled) >= 0.6 * max_w and score > best_score + 0.15:
            best, best_score = i, score
            if score > 4.2:
                break
    return best


def grid_to_df(grid: list[list[str]]) -> pd.DataFrame:
    if not grid:
        return pd.DataFrame()
    h = find_header_row(grid)
    header = [str(c).strip() for c in grid[h]]
    body = grid[h + 1:]
    width = max(len(header), max((len(r) for r in body), default=0))
    header = header + [""] * (width - len(header))
    # name blank or duplicate headers
    seen: dict[str, int] = {}
    cols = []
    for j, c in enumerate(header):
        c = c or f"Column {j + 1}"
        if c in seen:
            seen[c] += 1
            c = f"{c} ({seen[c]})"
        else:
            seen[c] = 1
        cols.append(c)
    rows = [list(r) + [""] * (width - len(r)) for r in body]
    df = pd.DataFrame(rows, columns=cols, dtype=object)
    df = df.map(lambda v: None if v is None or (isinstance(v, str) and not v.strip()) else v)
    df = df.dropna(how="all")  # blank rows
    df = df.dropna(axis=1, how="all") if len(df) else df
    # drop repeated header rows and subtotal rows that echo the header
    if len(df):
        mask = df.astype(str).apply(lambda r: sum(a == b for a, b in zip(r, df.columns)) > len(df.columns) / 2, axis=1)
        df = df[~mask]
    df.attrs["header_row"] = h
    df.attrs["first_data_row"] = h + 2  # 1-based line number of first data row
    return df.reset_index(drop=True)


def read_delimited(text: str, delimiter: str | None = None) -> pd.DataFrame:
    delim = delimiter or _sniff_delimiter(text)
    grid = list(csv.reader(io.StringIO(text), delimiter=delim))
    df = grid_to_df(grid)
    df.attrs["delimiter"] = {",": "comma", ";": "semicolon", "\t": "tab", "|": "pipe"}.get(delim, delim)
    return df


def split_messages(text: str) -> list[str]:
    """Pasted messages: one item per paragraph; if there are no blank lines, one per line."""
    text = text.replace("\r\n", "\n").strip()
    if not text:
        return []
    parts = re.split(r"\n\s*\n", text)
    if len(parts) == 1:
        parts = text.split("\n")
    out = []
    for p in parts:
        p = re.sub(r"^\s*(\[\d{1,2}[/:.]\d{1,2}.*?\]|\d{1,2}/\d{1,2}/\d{2,4},? \d{1,2}:\d{2}\s*-?)\s*", "", p.strip())  # chat timestamps
        p = re.sub(r"^[-*•]\s+", "", p)
        if len(p) >= 3:
            out.append(" ".join(p.split()))
    return out


def text_to_table(text: str, name: str) -> RawTable:
    msgs = split_messages(text)
    df = pd.DataFrame({"Message": msgs}, dtype=object)
    return RawTable(name=name, df=df, file_name=name, kind_hint="text",
                    notes=[f"Split into {len(msgs)} messages (one per paragraph)."])


def _flatten_json(obj) -> list[dict]:
    if isinstance(obj, list):
        if obj and all(isinstance(x, dict) for x in obj):
            return obj
        return [{"value": x} for x in obj]
    if isinstance(obj, dict):
        # find the biggest list of records inside (Graph API style {"data": [...]})
        lists = [(k, v) for k, v in obj.items() if isinstance(v, list) and v and isinstance(v[0], dict)]
        if lists:
            return max(lists, key=lambda kv: len(kv[1]))[1]
        return [obj]
    return [{"value": obj}]


def read_file(file_name: str, data: bytes) -> list[RawTable]:
    ext = Path(file_name).suffix.lower()
    if ext == ".zip":
        return read_zip(file_name, data)
    if ext in {".csv", ".tsv"}:
        text = decode(data)
        df = read_delimited(text, "\t" if ext == ".tsv" else None)
        return [RawTable(file_name, df, file_name)]
    if ext in {".xlsx", ".xlsm", ".xls"}:
        return read_excel(file_name, data)
    if ext in {".json", ".jsonl", ".ndjson"}:
        text = decode(data)
        try:
            if ext == ".json":
                recs = _flatten_json(json.loads(text))
            else:
                recs = [json.loads(ln) for ln in text.splitlines() if ln.strip()]
        except json.JSONDecodeError as e:
            raise ReadError(f"This JSON file looks damaged near line {e.lineno}. Try exporting it again.") from e
        df = pd.json_normalize(recs, sep=" ").astype(object)
        df = df.where(pd.notna(df), None)
        return [RawTable(file_name, df, file_name)]
    if ext in TEXT_EXT:
        text = decode(data)
        # a pasted table? (several lines with the same delimiter count)
        lines = [ln for ln in text.splitlines() if ln.strip()]
        for d in ("\t", ";", ","):
            counts = [ln.count(d) for ln in lines[:20]]
            if len(lines) > 2 and counts and min(counts) >= 1 and len(set(counts)) == 1:
                return [RawTable(file_name, read_delimited(text, d), file_name)]
        return [text_to_table(text, file_name)]
    if ext == ".pdf":
        return read_pdf(file_name, data)
    if ext == ".docx":
        return read_docx(file_name, data)
    if ext in IMAGE_EXT:
        return [RawTable(file_name, pd.DataFrame(), file_name, kind_hint="image")]
    # unknown extension: try text
    try:
        text = data.decode("utf-8")
        return [RawTable(file_name, read_delimited(text), file_name)]
    except UnicodeDecodeError:
        raise ReadError(f"We cannot read '{ext or 'this'}' files yet. Try CSV, Excel, JSON, PDF, Word, text, ZIP or a screenshot.")


def read_excel(file_name: str, data: bytes) -> list[RawTable]:
    ext = Path(file_name).suffix.lower()
    engine = "xlrd" if ext == ".xls" else "openpyxl"
    try:
        sheets = pd.read_excel(io.BytesIO(data), sheet_name=None, header=None, dtype=object, engine=engine)
    except Exception as e:  # noqa: BLE001
        raise ReadError("We could not open this spreadsheet. If it is password-protected, remove the password and try again.") from e
    out = []
    for sheet, raw in sheets.items():
        raw = raw.dropna(how="all").dropna(axis=1, how="all")
        if raw.empty:
            continue
        grid = raw.astype(object).where(pd.notna(raw), "").values.tolist()
        grid = [[c if not isinstance(c, float) or not c.is_integer() else int(c) for c in r] for r in grid]
        # keep datetimes as objects; stringify the rest
        grid = [[c if hasattr(c, "year") else ("" if c == "" else str(c)) for c in r] for r in grid]
        df = grid_to_df(grid)
        if df.empty:
            continue
        out.append(RawTable(f"{file_name} · {sheet}", df, file_name, sheet=str(sheet)))
    if not out:
        raise ReadError("This workbook has no data in any sheet.")
    return out


def read_pdf(file_name: str, data: bytes) -> list[RawTable]:
    import pdfplumber

    tables, texts = [], []
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for page in pdf.pages[:60]:
                for t in page.extract_tables() or []:
                    if t and len(t) > 1:
                        tables.append([[c or "" for c in r] for r in t])
                texts.append(page.extract_text() or "")
    except Exception as e:  # noqa: BLE001
        raise ReadError("We could not read this PDF. If it is a scan, upload it as an image instead.") from e
    out = [RawTable(f"{file_name} · table {i + 1}", grid_to_df(g), file_name, sheet=f"table {i + 1}") for i, g in enumerate(tables)]
    body = "\n\n".join(texts).strip()
    if body and not out:
        out.append(text_to_table(body, file_name))
    if not out:
        raise ReadError("This PDF has no readable text. It may be a scanned image; try a screenshot upload with AI analysis on.")
    return out


def read_docx(file_name: str, data: bytes) -> list[RawTable]:
    import docx

    d = docx.Document(io.BytesIO(data))
    out = []
    for i, t in enumerate(d.tables):
        grid = [[c.text for c in r.cells] for r in t.rows]
        if len(grid) > 1:
            out.append(RawTable(f"{file_name} · table {i + 1}", grid_to_df(grid), file_name, sheet=f"table {i + 1}"))
    paras = "\n\n".join(p.text for p in d.paragraphs if p.text.strip())
    if paras:
        out.append(text_to_table(paras, file_name))
    if not out:
        raise ReadError("This Word document is empty.")
    return out


def read_zip(file_name: str, data: bytes) -> list[RawTable]:
    out = []
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for info in z.infolist()[:100]:
            if info.is_dir() or info.filename.startswith("__MACOSX") or Path(info.filename).name.startswith("."):
                continue
            inner = Path(info.filename).name
            try:
                out.extend(read_file(inner, z.read(info)))
            except ReadError:
                continue
    if not out:
        raise ReadError("We did not find any readable files inside this ZIP.")
    return out
