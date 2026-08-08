# Headlight CRM

A small, self-contained CRM for a **headlight restoration** business.
Track customers, jobs (appointments), payments, and see money-in vs. profit at a glance.
Mobile-friendly and designed to run on a phone in the field.

## Features
- **Dashboard** — customers, jobs, collected, outstanding, profit, upcoming & recent jobs.
- **Customers** — name, phone, email, vehicle, address, notes; one tap to call/email.
- **Jobs** — service type, date, status (Scheduled / In Progress / Completed / Cancelled), price, cost.
- **Payments** — record cash / card / Venmo / Zelle / check; auto-calculates balance due.
- **Offline-friendly data** — a single SQLite file in `data/crm.db` (no external database server).
- **Optional password** — set `CRM_PASSWORD` to gate the whole app.

## Run locally (development)

```bash
cd headlight-crm
pip install -r requirements.txt
python run.py
# open http://localhost:5000
```

> **Use `run.py`, not `python app.py`.** On some setups Flask's built-in
> dev server (`app.run()`) skips `before_request` hooks, leaving the app
> unauthenticated. `run.py` serves via **waitress** — the same server used in
> production — so auth works correctly. The first launch prints an
> auto-generated password (or set `CRM_PASSWORD`).

To load demo data once:
```python
python -c "import models, models as m; m.init_db(); m.seed_demo()"
```

## Deploy to Render (free, phone-accessible)

1. Push this folder to a GitHub repo.
2. In Render, *New > Web Service* → connect the repo.
   - Build command: `pip install -r requirements.txt`
   - Start command: `waitress-serve --port=$PORT app:app`
   - (Or just import `render.yaml` — it sets exactly this.)
3. **Add a managed Postgres database** (the recommended, zero-friction option):
   - *New > PostgreSQL* → create it, then on your **Web Service** add
     an environment variable `DATABASE_URL` and set it to the Postgres
     instance's **internal** connection string (`postgres://...:5432/...`),
     not the external one.
   - The app uses Postgres automatically when `DATABASE_URL` is set, and the
     data **survives restarts with no disk required**.
4. **Set a password** (the app is never world-open):
   - Set `CRM_PASSWORD` to your own passphrase. If you leave it blank, the app
     auto-generates a strong one, prints it to the logs, and persists it in the
     DB (so it survives restarts). Set `CRM_PASSWORD` to control it yourself.
5. Open the generated `https://<your-service>.onrender.com` on your phone.

> **Alternative (no DB service):** keep SQLite by attaching a 1 GB persistent
> disk at `/var/data` and setting `CRM_DB_PATH=/var/data/crm.db`. Postgres is
> preferred because it's managed and needs no disk.

## Security model
- The whole app is gated behind a single password. There is **no "open" mode in
  production** — if `CRM_PASSWORD` is unset, a strong one is generated and logged.
- Login is brute-force protected (5 tries per IP, then a 1-minute lockout) and
  uses constant-time password comparison.
- Session cookies are hardened (`HttpOnly`, `SameSite=Lax`, `Secure` on HTTPS).

## Environment variables
| Var | Purpose | Default |
|-----|---------|---------|
| `SECRET_KEY` | Flask session signing | random per-boot (set for stable sessions) |
| `CRM_PASSWORD` | App password. If blank, a strong one is auto-generated + logged | (none = auto-gen) |
| `DATABASE_URL` | Postgres connection string. **If set, Postgres is used** (managed, survives restarts) | (none → SQLite) |
| `CRM_DB_PATH` | SQLite file location (only used when `DATABASE_URL` is unset) | `data/crm.db` |
| `PORT` | Listen port (hosts set this) | 5000 |
| `SECURE_COOKIES` | Set `0` only if serving over plain HTTP behind no TLS | `1` |

## Project layout
```
app.py            Flask routes + auth (single-password, brute-force protected)
models.py         Data layer — Postgres (DATABASE_URL) or SQLite fallback
templates/        Mobile-responsive HTML pages
data/crm.db       SQLite database (only when DATABASE_URL is unset)
requirements.txt  Flask + waitress + psycopg
```
