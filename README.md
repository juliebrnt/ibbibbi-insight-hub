# iBBIBBI Insight Hub

**Try the prototype:** https://juliebrnt.github.io/ibbibbi-insight-hub/ (demo data, made-up customers; switch to *Mine* to see the first-day screen)

Drop in any data the founders have (Shopify, Instagram, TikTok, Google Analytics, Klaviyo, surveys, pasted messages, any spreadsheet) and get clear charts, plain-language insights, recommended actions, a question box and a plan that tracks what was decided and learned. Works on a laptop and on a phone. Data stays on the machine.

## Quick start
1. Install Python 3.11+ and Node 18+ (on a Mac: `brew install python@3.12 node`).
2. `make run`: installs everything, builds, and serves the app at http://localhost:8000
3. `make demo`: generates and loads the demo workspace (or press "Load demo data" in the app).
4. Optional: copy `.env.example` to `.env` and add `ANTHROPIC_API_KEY` for the AI features.
5. `make dev` for hot reload (http://localhost:5173), `make test` for the tests.

## Prototype (no install needed)
`make prototype` builds `docs/index.html` (published with GitHub Pages) and `prototype/index.html` (for a Claude artifact): the real app running on saved snapshots of the demo data, so anyone can click through it in a browser. **Demo data** shows the app full of sample customers; **My data** shows the first-day screen the founders see before uploading anything. Nothing is saved in the prototype.

## What is where
- `backend/app/ingest`: reading any file, header detection, EU formats, classification, mapping, recipes, validation, undo, flexible datasets
- `backend/app/privacy`: personal-data detection, hashing, scrubbing before AI
- `backend/app/analytics`: sales, feedback, social, web, cross-source, metrics
- `backend/app/insights`: rules engine, plan (goals, decisions, learning log), weekly briefing
- `backend/app/ai`: the only place that calls an AI provider; number guard; Ask with SQL validator
- `frontend/src`: React app (pages, components, charts, theme tokens)
- `scripts/generate_demo_data.py`: seeded, messy, realistic demo exports in `demo_data/`

## Rebranding (five minutes)
- Colours: `frontend/src/theme/tokens.css` (RGB triplets) and `frontend/src/theme/tokens.ts`.
- Logo: replace `assets/logo.svg` and `frontend/public/favicon.svg`, then run `.venv/bin/python scripts/make_icons.py` (or drop in your own `icon-192.png`, `icon-512.png`, `apple-touch-icon.png`).

## Privacy
Names and addresses are not stored; emails and phones become salted anonymous ids. The system never infers anyone's health status or treatment stage. Distress messages are flagged for a personal reply, never for marketing. Text is scrubbed before any AI call, and AI can be switched off in Settings. Export and delete everything from Settings.
