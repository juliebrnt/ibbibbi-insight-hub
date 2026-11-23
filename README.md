# iBBIBBI Insight Hub

**Try the prototype:** https://juliebrnt.github.io/ibbibbi-insight-hub/ (demo data, made-up customers; switch to *Mine* to see the first-day screen)

A business intelligence platform for any small business, set up here for iBBIBBI. Drop in any data (Shopify, Instagram, TikTok, Google Analytics, Klaviyo, surveys, pasted messages, any spreadsheet) and get clear charts, plain-language insights, recommended actions, a question box and a plan that tracks what was decided and learned. Works on a laptop and on a phone. Data stays on the machine.

## Quick start
1. Install Python 3.11+ and Node 18+ (on a Mac: `brew install python@3.12 node`).
2. `make run`: installs everything, builds, and serves the app at http://localhost:8000
3. `make demo`: generates and loads the demo workspace (or press "Load demo data" in the app).
4. Optional: copy `.env.example` to `.env` and add `ANTHROPIC_API_KEY` for the AI features.
5. `make dev` for hot reload (http://localhost:5173), `make test` for the tests.

## Prototype (no install needed)
`make prototype` builds `docs/index.html` (published with GitHub Pages) and `prototype/index.html` (for a Claude artifact): the real app running on saved snapshots of the demo data, so anyone can click through it in a browser. **Demo data** shows the app full of sample customers; **My data** shows the first-day screen the founders see before uploading anything. Nothing is saved in the prototype.

## Highlights
- **Integrations:** Shopify and Judge.me connect live with a key the store owner creates (no platform review); everything else uploads as files. Instagram, TikTok, LinkedIn and Amazon show their real requirements and stay "Coming soon" until their app reviews are done.
- **Feedback:** every review, survey answer, message and comment in one filterable list, grouped into categories; replies publish to Judge.me directly, other platforms get an editable draft.
- **Alerts, cross-channel checks and recommendations**, each with its evidence, calculation and how to measure success.
- **English and Spanish:** EN/ES in the top bar (More menu on phones). One shared catalogue in `shared/i18n/` translates the interface, generated insights, alerts and the exported briefing. `python scripts/harvest_strings.py` reports coverage and lists anything new to translate.
- **Any business:** Settings, Business profile sets the name, industry, mission, key dates and whether customers may be vulnerable.
- **Hosting:** see `DEPLOY.md` (Render, EU region, password sign-in, encrypted keys).

## What is where
- `backend/app/ingest`: reading any file, header detection, EU formats, classification, mapping, recipes, validation, undo, flexible datasets
- `backend/app/privacy`: personal-data detection, hashing, scrubbing before AI
- `backend/app/analytics`: sales, feedback, social, web, cross-source, metrics
- `backend/app/insights`: rules engine, plan (goals, decisions, learning log), weekly briefing
- `backend/app/ai`: the only place that calls an AI provider; number guard; Ask with SQL validator
- `backend/app/integrations.py`, `backend/app/models/connectors.py`: integration registry, live Shopify and Judge.me connectors, encrypted key storage
- `shared/`: translation catalogue (`i18n/es*.json`) and the matching rules used by the backend (`i18n_core.py`) and the screens (`frontend/src/lib/i18n.ts`)
- `frontend/src`: React app (pages, components, charts, theme tokens)
- `scripts/generate_demo_data.py`: seeded, messy, realistic demo exports in `demo_data/`

## Rebranding (five minutes)
- Colours: `frontend/src/theme/tokens.css` (RGB triplets) and `frontend/src/theme/tokens.ts`.
- Logo: replace `assets/logo.svg` and `frontend/public/favicon.svg`, then run `.venv/bin/python scripts/make_icons.py` (or drop in your own `icon-192.png`, `icon-512.png`, `apple-touch-icon.png`).

## Privacy
Names and addresses are not stored; emails and phones become salted anonymous ids. The system never infers anyone's health status or treatment stage. Distress messages are flagged for a personal reply, never for marketing. Text is scrubbed before any AI call, and AI can be switched off in Settings. Export and delete everything from Settings.
