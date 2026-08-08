"""
Data layer for the Headlight Restoration CRM.

Backends:
  - Postgres when DATABASE_URL is set (managed DB, survives restarts — use on Render).
  - SQLite otherwise (zero-config local dev / fallback).

All public function signatures are backend-agnostic. Queries are written with
Postgres-style `%s` placeholders and adapted to `?` for SQLite.
"""
import os

DATABASE_URL = os.environ.get("DATABASE_URL")
USE_PG = bool(DATABASE_URL)

if USE_PG:
    import psycopg  # noqa: E402

DB_PATH = os.environ.get(
    "CRM_DB_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "crm.db"),
)


def _sql(sql):
    """Convert Postgres %s placeholders to SQLite ? when needed."""
    return sql if USE_PG else sql.replace("%s", "?")


def get_conn():
    if USE_PG:
        return psycopg.connect(DATABASE_URL)
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    import sqlite3
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    return c


def _cols(cur):
    return [d[0] for d in cur.description]


def _rows(cur):
    if cur.description is None:
        return []
    cols = _cols(cur)
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def _one(cur):
    rows = _rows(cur)
    return rows[0] if rows else None


# ------------------------------- Schema -------------------------------

_SQLITE_DDL = """
CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT, email TEXT, address TEXT, vehicle TEXT, notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    job_date TEXT,
    status TEXT NOT NULL DEFAULT 'Scheduled',
    service_type TEXT,
    price REAL NOT NULL DEFAULT 0,
    cost REAL NOT NULL DEFAULT 0,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    amount REAL NOT NULL,
    method TEXT,
    pay_date TEXT,
    note TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""

_PG_DDL = """
CREATE TABLE IF NOT EXISTS customers (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    phone TEXT, email TEXT, address TEXT, vehicle TEXT, notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS jobs (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    job_date TEXT,
    status TEXT NOT NULL DEFAULT 'Scheduled',
    service_type TEXT,
    price REAL NOT NULL DEFAULT 0,
    cost REAL NOT NULL DEFAULT 0,
    notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS payments (
    id SERIAL PRIMARY KEY,
    job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    amount REAL NOT NULL,
    method TEXT,
    pay_date TEXT,
    note TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    ddl = _PG_DDL if USE_PG else _SQLITE_DDL
    for stmt in ddl.split(";"):
        stmt = stmt.strip()
        if stmt:
            cur.execute(stmt)
    conn.commit()
    conn.close()


# ------------------------------ Settings ------------------------------

def get_setting(key, default=None):
    conn = get_conn()
    cur = conn.execute(_sql("SELECT value FROM meta WHERE key=%s"), (key,))
    row = _one(cur)
    conn.close()
    return row["value"] if row else default


def set_setting(key, value):
    conn = get_conn()
    conn.execute(
        _sql("INSERT INTO meta(key, value) VALUES(%s, %s) "
             "ON CONFLICT(key) DO UPDATE SET value=excluded.value"),
        (key, str(value)),
    )
    conn.commit()
    conn.close()


# ----------------------------- Customers -----------------------------

def customer_create(name, phone="", email="", address="", vehicle="", notes=""):
    conn = get_conn()
    cur = conn.execute(
        _sql("INSERT INTO customers (name, phone, email, address, vehicle, notes) "
             "VALUES (%s,%s,%s,%s,%s,%s) RETURNING id"),
        (name, phone, email, address, vehicle, notes),
    )
    cid = cur.fetchone()[0]
    conn.commit()
    conn.close()
    return cid


def customer_update(cid, **fields):
    allowed = {"name", "phone", "email", "address", "vehicle", "notes"}
    sets = {k: v for k, v in fields.items() if k in allowed}
    if not sets:
        return False
    cols = ", ".join(f"{k}=%s" for k in sets)
    conn = get_conn()
    conn.execute(_sql(f"UPDATE customers SET {cols} WHERE id=%s"),
                 list(sets.values()) + [cid])
    conn.commit()
    conn.close()
    return True


def customer_delete(cid):
    conn = get_conn()
    conn.execute(_sql("DELETE FROM customers WHERE id=%s"), (cid,))
    conn.commit()
    conn.close()


def customer_get(cid):
    conn = get_conn()
    cur = conn.execute(_sql("SELECT * FROM customers WHERE id=%s"), (cid,))
    row = _one(cur)
    conn.close()
    return row


def customers_all():
    conn = get_conn()
    cur = conn.execute("SELECT * FROM customers ORDER BY LOWER(name)")
    rows = _rows(cur)
    conn.close()
    return rows


# ------------------------------- Jobs -------------------------------

def job_create(customer_id, job_date="", status="Scheduled", service_type="",
               price=0, cost=0, notes=""):
    conn = get_conn()
    cur = conn.execute(
        _sql("INSERT INTO jobs (customer_id, job_date, status, service_type, price, cost, notes) "
             "VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id"),
        (customer_id, job_date, status, service_type, price, cost, notes),
    )
    jid = cur.fetchone()[0]
    conn.commit()
    conn.close()
    return jid


def job_update(jid, **fields):
    allowed = {"customer_id", "job_date", "status", "service_type",
               "price", "cost", "notes"}
    sets = {k: v for k, v in fields.items() if k in allowed}
    if not sets:
        return False
    cols = ", ".join(f"{k}=%s" for k in sets)
    conn = get_conn()
    conn.execute(_sql(f"UPDATE jobs SET {cols} WHERE id=%s"),
                 list(sets.values()) + [jid])
    conn.commit()
    conn.close()
    return True


def job_delete(jid):
    conn = get_conn()
    conn.execute(_sql("DELETE FROM jobs WHERE id=%s"), (jid,))
    conn.commit()
    conn.close()


def job_get(jid):
    conn = get_conn()
    cur = conn.execute(_sql("SELECT * FROM jobs WHERE id=%s"), (jid,))
    row = _one(cur)
    conn.close()
    return row


def jobs_all():
    conn = get_conn()
    cur = conn.execute(
        "SELECT j.*, c.name AS customer_name, c.phone AS customer_phone "
        "FROM jobs j JOIN customers c ON c.id = j.customer_id "
        "ORDER BY COALESCE(j.job_date, '9999-12-31') DESC, j.id DESC"
    )
    rows = _rows(cur)
    conn.close()
    return rows


def jobs_for_customer(cid):
    conn = get_conn()
    cur = conn.execute(
        _sql("SELECT * FROM jobs WHERE customer_id=%s "
             "ORDER BY COALESCE(job_date,'9999-12-31') DESC"),
        (cid,),
    )
    rows = _rows(cur)
    conn.close()
    return rows


# ----------------------------- Payments -----------------------------

def payment_create(job_id, amount, method="", pay_date="", note=""):
    conn = get_conn()
    cur = conn.execute(
        _sql("INSERT INTO payments (job_id, amount, method, pay_date, note) "
             "VALUES (%s,%s,%s,%s,%s) RETURNING id"),
        (job_id, amount, method, pay_date, note),
    )
    pid = cur.fetchone()[0]
    conn.commit()
    conn.close()
    return pid


def payment_delete(pid):
    conn = get_conn()
    conn.execute(_sql("DELETE FROM payments WHERE id=%s"), (pid,))
    conn.commit()
    conn.close()


def payments_for_job(jid):
    conn = get_conn()
    cur = conn.execute(
        _sql("SELECT * FROM payments WHERE job_id=%s "
             "ORDER BY COALESCE(pay_date,'9999-12-31') DESC, id DESC"),
        (jid,),
    )
    rows = _rows(cur)
    conn.close()
    return rows


# ---------------------------- Dashboard -----------------------------

def dashboard_stats():
    conn = get_conn()
    s = {}
    s["customers"] = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
    s["jobs"] = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    s["completed_jobs"] = conn.execute(
        "SELECT COUNT(*) FROM jobs WHERE status='Completed'").fetchone()[0]

    rev = conn.execute("SELECT COALESCE(SUM(amount),0) FROM payments").fetchone()[0]
    s["revenue"] = round(float(rev), 2)

    billed = conn.execute(
        "SELECT COALESCE(SUM(price),0) FROM jobs WHERE status='Completed'").fetchone()[0]
    s["billed"] = round(float(billed), 2)

    s["outstanding"] = round(s["billed"] - s["revenue"], 2)
    if s["outstanding"] < 0:
        s["outstanding"] = 0.0

    cost = conn.execute(
        "SELECT COALESCE(SUM(cost),0) FROM jobs WHERE status='Completed'").fetchone()[0]
    s["profit"] = round(s["billed"] - float(cost), 2)

    cur = conn.execute(
        "SELECT j.id, j.job_date, j.service_type, j.status, c.name AS customer_name "
        "FROM jobs j JOIN customers c ON c.id=j.customer_id "
        "WHERE j.status IN ('Scheduled','In Progress') "
        "ORDER BY COALESCE(j.job_date,'9999-12-31') ASC LIMIT 5"
    )
    upcoming = _rows(cur)

    cur = conn.execute(
        "SELECT j.id, j.job_date, j.service_type, j.status, j.price, c.name AS customer_name "
        "FROM jobs j JOIN customers c ON c.id=j.customer_id "
        "ORDER BY COALESCE(j.job_date,'9999-12-31') DESC, j.id DESC LIMIT 8"
    )
    recent = _rows(cur)

    conn.close()
    s["upcoming"] = upcoming
    s["recent"] = recent
    return s


def job_balance(jid):
    """Outstanding balance for a single job (price - payments)."""
    conn = get_conn()
    row = conn.execute(_sql("SELECT price FROM jobs WHERE id=%s"), (jid,)).fetchone()
    price = float(row[0]) if row else 0
    paid = conn.execute(
        _sql("SELECT COALESCE(SUM(amount),0) FROM payments WHERE job_id=%s"),
        (jid,)).fetchone()[0]
    conn.close()
    return round(price - float(paid), 2)


# ------------------------------ Demo ------------------------------

def seed_demo():
    """Optional demo data (idempotent-ish; only runs when DB is empty)."""
    if customers_all():
        return False
    c1 = customer_create("Sarah Mitchell", "555-0132", "sarah@example.com",
                         "120 Oak St", "2018 Honda Civic", "Found us on Google.")
    c2 = customer_create("Carlos Reyes", "555-0188", "", "45 Pine Ave",
                         "2015 Toyota Camry", "Prefers text reminders.")
    c3 = customer_create("Dana Whitfield", "555-0144", "dana@example.com",
                         "9 Lake Rd", "2020 Ford F-150", "")
    job_create(c1, "2026-08-10", "Scheduled", "Premium Restoration + Ceramic", 149.0, 18.0,
               "Mobile visit, bring ladder.")
    job_create(c2, "2026-08-09", "Completed", "Standard Restoration", 89.0, 12.0, "")
    job_create(c3, "2026-08-12", "Scheduled", "Headlight + Taillight", 199.0, 25.0,
               "Both pairs yellowed.")
    payment_create(2, 89.0, "Card", "2026-08-09", "Paid in full")
    return True
