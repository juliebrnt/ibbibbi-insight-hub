# Test pack: check the app works before the founders use it

These files are **made up** (fake customers, `@example.com` emails) but shaped exactly like the exports the founders would download. They are a different set from the built-in demo, so you can test the real "first day" experience.

## How to test (about 15 minutes)

1. Start the app: `make run`, then open http://localhost:8000
2. At the top, switch to **My data**. Home should show the getting-started checklist.
3. Upload the folders in order, checking each step.

| Step | Upload | What should happen |
|---|---|---|
| 1 | Everything in `1_start_here` (select all four at once) | Recognised as Shopify orders, products, Judge.me reviews and Instagram. Names, addresses and phone numbers are marked "Do not store"; emails "Replace with anonymous id". |
| 2 | Look at **Home** | Key numbers, "What changed" and ranked recommendations appear. The checklist on the first-day screen is gone. |
| 3 | Everything in `2_add_more` | The two-sheet Excel becomes a survey and customer messages. The WhatsApp text file is split into separate messages. `mercadillo_ventas.csv` is not recognised and is kept as **your own dataset**. |
| 4 | Data page, then **Make a trend** on the market file | Pick Fecha and Caja (€). A "Market stalls" recommendation appears on Home. |
| 5 | Each file in `3_tricky_files`, one by one | See the next table. |
| 6 | Upload `1_start_here/pedidos_shopify_2026.csv` again | "Already there": nothing is counted twice, and revenue on Home does not change. |
| 7 | **Undo import** on any file (Data page) | Its numbers disappear from every page. |
| 8 | Open the address on your phone (same Wi-Fi, or once it is hosted) | Pages fit the screen; you can read every chart. |

### Tricky files

| File | Tests | Expected |
|---|---|---|
| `orders_odd_column_names.csv` | Unusual headers ("Order #", "Importe total"), semicolons, `1.234,56` amounts, `dd.mm.yyyy` dates | Shopify orders, ~90% sure, all 60 rows imported with correct euro amounts |
| `typeform_survey_english.csv` | English survey with a 0 to 10 question | Survey responses; NPS appears on Feedback |
| `shop_sales_with_title_rows.xlsx` | Title lines above the header, a blank row and a TOTAL line | Header found on the right row; TOTAL is not counted |
| `market_day_notes.docx` | A Word document of notes | Each paragraph becomes a piece of feedback |
| `export_bundle.zip` | A ZIP containing files you already uploaded | Both files read; reported as "already there" |
| `empty_file.csv` | An empty file | A clear message: "This file is empty…" (no crash) |

### Also check
- **Numbers match the source.** In Sales, compare revenue for one month with the same month in the CSV (open it in Excel and add up the Total column). They should match to the euro.
- **Privacy.** Data page → preview a dataset: no names or emails, only ids like `c_3f9a…`.
- **Care messages.** Feedback shows a "Consider a personal reply" box for messages from people having a hard time.
- **Ask.** Try "Which products get the best reviews?" and open "How I got this".

## Before giving it to the founders

**Data and privacy**
- [ ] Test with **one real export from the founders** first (for example last month's Shopify orders). Real files can have columns the test pack does not.
- [ ] Agree where the data lives: on their laptop, or on a hosted server with a password. If hosted, use an EU region (GDPR) and set `APP_PASSWORD`.
- [ ] Their privacy notice should mention that order and feedback data is analysed in aggregate.
- [ ] Only switch AI on (API key) if the founders agree to anonymised text being sent to the AI provider. Everything works without it.
- [ ] Customers' quotes are only used publicly when "OK to quote" is ticked.

**Running it**
- [ ] Decide who looks after it (updates, backups, help) once the course ends.
- [ ] Show the founders the 15-minute weekly routine: upload new exports, read Home, review the Plan, export the briefing.
- [ ] Export a backup now and then (Settings → Export everything).

**Expectations**
- [ ] Insights are only as good as the data. With little data, the app says "not enough data yet" instead of guessing.
- [ ] Links between content and sales are **correlations**, not proof.
- [ ] The app never guesses anyone's health or treatment stage, and never suggests targeting people that way.
