PY ?= .venv/bin/python
PIP ?= .venv/bin/pip

.PHONY: setup dev run demo test build prototype

.venv:
	python3.12 -m venv .venv || python3 -m venv .venv
	$(PIP) install -q -r backend/requirements.txt

frontend/node_modules:
	cd frontend && npm install

setup: .venv frontend/node_modules

build: setup
	cd frontend && npm run build

dev: setup ## backend + Vite with hot reload (open http://localhost:5173)
	@(cd backend && ../$(PY) -m uvicorn app.main:app --reload --port 8000) & (cd frontend && npm run dev); wait

run: build ## build the frontend and serve everything at http://localhost:8000
	cd backend && ../$(PY) -m uvicorn app.main:app --port 8000

demo: setup ## regenerate demo files and load them into the Demo workspace
	$(PY) scripts/generate_demo_data.py
	cd backend && ../$(PY) -c "from app.demo.loader import load; r = load(); print(f\"Loaded {len(r['files'])} demo files\")"

test: setup
	cd backend && ../$(PY) -m pytest -q -p no:warnings tests

prototype: setup ## build a shareable, self-contained prototype with demo data into prototype/
	$(PY) scripts/export_prototype.py
