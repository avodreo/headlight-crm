"""
Data layer for the Headlight Restoration CRM.
Uses SQLite (no external DB server required) via the standard library.
"""
import os
import sqlite3

DB_PATH = os.environ.get(
    "CRM_DB_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "crm.db"),
)


def get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            email TEXT,
            address TEXT,
            vehicle TEXT,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    cur.execute(
        """
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
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
            amount REAL NOT NULL,
            method TEXT,
            pay_date TEXT,
            note TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def get_setting(key, default=None):
    conn = get_conn()
    row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default


def set_setting(key, value):
    conn = get_conn()
    conn.execute(
        "INSERT INTO meta(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, str(value)),
    )
    conn.commit()
    conn.close()


# ----------------------------- Customers -----------------------------

def customer_create(name, phone="", email="", address="", vehicle="", notes=""):
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO customers (name, phone, email, address, vehicle, notes) "
        "VALUES (?,?,?,?,?,?)",
        (name, phone, email, address, vehicle, notes),
    )
    conn.commit()
    cid = cur.lastrowid
    conn.close()
    return cid


def customer_update(cid, **fields):
    allowed = {"name", "phone", "email", "address", "vehicle", "notes"}
    sets = {k: v for k, v in fields.items() if k in allowed}
    if not sets:
        return False
    sql = "UPDATE customers SET " + ", ".join(f"{k}=?" for k in sets) + " WHERE id=?"
    conn = get_conn()
    conn.execute(sql, list(sets.values()) + [cid])
    conn.commit()
    conn.close()
    return True


def customer_delete(cid):
    conn = get_conn()
    conn.execute("DELETE FROM customers WHERE id=?", (cid,))
    conn.commit()
    conn.close()


def customer_get(cid):
    conn = get_conn()
    row = conn.execute("SELECT * FROM customers WHERE id=?", (cid,)).fetchone()
    conn.close()
    return dict(row) if row else None


def customers_all():
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM customers ORDER BY name COLLATE NOCASE"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ------------------------------- Jobs -------------------------------

def job_create(customer_id, job_date="", status="Scheduled", service_type="",
               price=0, cost=0, notes=""):
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO jobs (customer_id, job_date, status, service_type, price, cost, notes) "
        "VALUES (?,?,?,?,?,?,?)",
        (customer_id, job_date, status, service_type, price, cost, notes),
    )
    conn.commit()
    jid = cur.lastrowid
    conn.close()
    return jid


def job_update(jid, **fields):
    allowed = {"customer_id", "job_date", "status", "service_type",
               "price", "cost", "notes"}
    sets = {k: v for k, v in fields.items() if k in allowed}
    if not sets:
        return False
    sql = "UPDATE jobs SET " + ", ".join(f"{k}=?" for k in sets) + " WHERE id=?"
    conn = get_conn()
    conn.execute(sql, list(sets.values()) + [jid])
    conn.commit()
    conn.close()
    return True


def job_delete(jid):
    conn = get_conn()
    conn.execute("DELETE FROM jobs WHERE id=?", (jid,))
    conn.commit()
    conn.close()


def job_get(jid):
    conn = get_conn()
    row = conn.execute("SELECT * FROM jobs WHERE id=?", (jid,)).fetchone()
    conn.close()
    return dict(row) if row else None


def jobs_all():
    conn = get_conn()
    rows = conn.execute(
        "SELECT j.*, c.name AS customer_name, c.phone AS customer_phone "
        "FROM jobs j JOIN customers c ON c.id = j.customer_id "
        "ORDER BY COALESCE(j.job_date, '9999-12-31') DESC, j.id DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def jobs_for_customer(cid):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM jobs WHERE customer_id=? ORDER BY COALESCE(job_date,'9999-12-31') DESC",
        (cid,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ----------------------------- Payments -----------------------------

def payment_create(job_id, amount, method="", pay_date="", note=""):
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO payments (job_id, amount, method, pay_date, note) "
        "VALUES (?,?,?,?,?)",
        (job_id, amount, method, pay_date, note),
    )
    conn.commit()
    pid = cur.lastrowid
    conn.close()
    return pid


def payment_delete(pid):
    conn = get_conn()
    conn.execute("DELETE FROM payments WHERE id=?", (pid,))
    conn.commit()
    conn.close()


def payments_for_job(jid):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM payments WHERE job_id=? ORDER BY COALESCE(pay_date,'9999-12-31') DESC, id DESC",
        (jid,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------- Dashboard -----------------------------

def dashboard_stats():
    conn = get_conn()
    stats = {}
    stats["customers"] = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
    stats["jobs"] = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    stats["completed_jobs"] = conn.execute(
        "SELECT COUNT(*) FROM jobs WHERE status='Completed'").fetchone()[0]

    # Revenue = sum of payments
    rev = conn.execute("SELECT COALESCE(SUM(amount),0) FROM payments").fetchone()[0]
    stats["revenue"] = round(rev, 2)

    # Total billed = sum of prices on completed jobs
    billed = conn.execute(
        "SELECT COALESCE(SUM(price),0) FROM jobs WHERE status='Completed'").fetchone()[0]
    stats["billed"] = round(billed, 2)

    # Outstanding = billed - revenue (for completed jobs)
    stats["outstanding"] = round(stats["billed"] - stats["revenue"], 2)
    if stats["outstanding"] < 0:
        stats["outstanding"] = 0.0

    # Profit = billed - sum of costs on completed jobs
    cost = conn.execute(
        "SELECT COALESCE(SUM(cost),0) FROM jobs WHERE status='Completed'").fetchone()[0]
    stats["profit"] = round(stats["billed"] - cost, 2)

    # Upcoming (scheduled, future or no date)
    upcoming = conn.execute(
        "SELECT j.id, j.job_date, j.service_type, j.status, c.name AS customer_name "
        "FROM jobs j JOIN customers c ON c.id=j.customer_id "
        "WHERE j.status IN ('Scheduled','In Progress') "
        "ORDER BY COALESCE(j.job_date,'9999-12-31') ASC LIMIT 5"
    ).fetchall()

    recent = conn.execute(
        "SELECT j.id, j.job_date, j.service_type, j.status, j.price, c.name AS customer_name "
        "FROM jobs j JOIN customers c ON c.id=j.customer_id "
        "ORDER BY COALESCE(j.job_date,'9999-12-31') DESC, j.id DESC LIMIT 8"
    ).fetchall()

    conn.close()
    stats["upcoming"] = [dict(r) for r in upcoming]
    stats["recent"] = [dict(r) for r in recent]
    return stats


def job_balance(jid):
    """Outstanding balance for a single job (price - payments)."""
    conn = get_conn()
    price = conn.execute("SELECT price FROM jobs WHERE id=?", (jid,)).fetchone()
    price = price[0] if price else 0
    paid = conn.execute(
        "SELECT COALESCE(SUM(amount),0) FROM payments WHERE job_id=?", (jid,)).fetchone()[0]
    conn.close()
    return round(price - paid, 2)


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
