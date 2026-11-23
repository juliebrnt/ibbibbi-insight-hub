# Putting Insight Hub online for a company

About 20 minutes, once. After this the founders open a normal web address on their laptop and phone, sign in with a password, connect Shopify and Judge.me, and upload the rest.

## How it is set up

- **One private copy per company.** Each company gets its own web service and its own disk, so data can never mix between companies. This is the simplest strong form of company-level separation.
- **EU region** (Frankfurt), for GDPR.
- **The prototype on GitHub Pages stays separate.** It only ever shows demo data; nothing real is stored there.
- **Secrets live in the host's settings, never in GitHub:** the team password, the key that encrypts Shopify and Judge.me access keys, and the optional AI key.

## Steps (Render)

1. Create a free account at https://render.com and connect your GitHub account (the repository can stay public; no secrets are in it).
2. Make the encryption key for stored platform keys. On any computer with Python:
   ```bash
   python3 -c "import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"
   ```
   Copy the result. Keep it safe: without it, saved Shopify and Judge.me connections cannot be read (they can simply be reconnected).
3. In Render: **New**, **Blueprint**, pick the `ibbibbi-insight-hub` repository. Render reads `render.yaml`.
4. When asked, fill in:
   - `APP_PASSWORD`: the password the founders will use to sign in (long and unique).
   - `CREDENTIALS_KEY`: the key from step 2.
   - `ANTHROPIC_API_KEY`: leave empty unless the founders agreed to AI analysis.
5. Click **Apply**. The first build takes about 5 minutes. Render gives an address like `https://insight-hub-xxxx.onrender.com` with HTTPS switched on.
6. Open it, sign in, switch to **My data**, set the **Business profile** in Settings, then go to **Integrations** and connect Shopify and Judge.me (5 minutes each, from a computer).
7. On the founders' phones: open the address in Safari or Chrome, then **Share**, **Add to Home Screen**. It works like an app.

## Costs

- Render web service with a disk: about 7 USD a month (the free tier has no persistent disk, so data would be lost on restart).
- Shopify custom app and Judge.me API: free.
- AI (optional): pay per use with Anthropic.

## Updating

Every push to GitHub's `main` branch redeploys automatically. Data on the disk is kept.

## Backups and deleting data

- Settings, **Export everything** downloads all data as a ZIP. Do this monthly.
- Settings, **Delete everything** removes all workspace data from the disk immediately. Render's own disk snapshots are kept for a short period by Render and then expire; deleted data is not restored unless a snapshot is restored on purpose.
- Disconnecting an integration deletes its stored access key. Also remove the custom app (Shopify) or regenerate the token (Judge.me) to revoke access on the platform side.

## Running it on your own computer instead

`make run` and open http://localhost:8000. Everything stays on that computer.
