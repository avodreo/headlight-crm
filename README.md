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
   - Start command: `gunicorn -w 2 -b 0.0.0.0:$PORT app:app`
   - (Or just import `render.yaml`.)
3. **Persistent disk** (important — SQLite lives on disk):
   - Add a Disk: Mount Path `/var/data`, size 1 GB.
   - Set env var `CRM_DB_PATH=/var/data/crm.db`.
4. Optional: set `CRM_PASSWORD` to protect the app, and `SECRET_KEY`.
5. Open the generated `https://<your-service>.onrender.com` on your phone.

> Without a persistent disk on Render, the free tier wipes the filesystem on each
> restart and you'd lose data. The disk keeps `crm.db` safe. Alternatively, swap
> `models.py` for Postgres (replace the `sqlite3` calls) for a fully managed DB.

## Environment variables
| Var | Purpose | Default |
|-----|---------|---------|
| `SECRET_KEY` | Flask session signing | dev key (change in prod) |
| `CRM_PASSWORD` | Gate the whole app (blank = open) | (none) |
| `CRM_DB_PATH` | SQLite file location | `data/crm.db` |
| `PORT` | Listen port (hosts set this) | 5000 |

## Project layout
```
app.py            Flask routes + auth
models.py         SQLite data layer (customers, jobs, payments)
templates/        Mobile-responsive HTML pages
data/crm.db       SQLite database (created automatically)
requirements.txt  Flask + gunicorn
```
