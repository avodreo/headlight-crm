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
python app.py
# open http://localhost:5000
```

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
3. **Persistent disk** (REQUIRED — SQLite lives on disk):
   - Add a Disk: Mount Path `/var/data`, size 1 GB.
   - Set env var `CRM_DB_PATH=/var/data/crm.db`.
   - Without this, the free tier wipes the filesystem on each restart and you
     lose all customers/jobs. The app also prints a startup WARNING if it
     detects a PaaS host without `CRM_DB_PATH` set.
4. **Set a password** (the app is never world-open):
   - Set `CRM_PASSWORD` to your own passphrase. If you leave it blank, the app
     auto-generates a strong one, prints it to the logs, and persists it in the
     DB (so it survives restarts). Set `CRM_PASSWORD` to control it yourself.
5. Open the generated `https://<your-service>.onrender.com` on your phone.

> Prefer a fully managed DB instead of a disk? Swap `models.py`'s sqlite3 calls
> for Postgres — the rest of the app is DB-agnostic.

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
| `CRM_DB_PATH` | SQLite file location. **Set to a persistent disk on PaaS** | `data/crm.db` |
| `PORT` | Listen port (hosts set this) | 5000 |
| `SECURE_COOKIES` | Set `0` only if serving over plain HTTP behind no TLS | `1` |

## Project layout
```
app.py            Flask routes + auth (single-password, brute-force protected)
models.py         SQLite data layer (customers, jobs, payments, settings)
templates/        Mobile-responsive HTML pages
data/crm.db       SQLite database (created automatically)
requirements.txt  Flask + waitress
```
