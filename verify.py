"""Self-contained smoke test for the Headlight CRM.
Exercises every route via Flask's test client. Run: python verify.py
"""
import os, tempfile, importlib
os.environ["CRM_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "test_crm.db")

import models
models.init_db()

import app as appmod
appmod.resolve_password()
PASSWORD = appmod.PASSWORD
client = appmod.app.test_client()

failures = []
def check(name, resp, want=200):
    ok = resp.status_code == want
    print(f"[{'OK' if ok else 'FAIL'}] {name} -> {resp.status_code}")
    if not ok:
        failures.append((name, resp.status_code))

def login():
    return client.post("/login", data={"password": PASSWORD})

# --- Auth: app is locked by default ---
check("GET / redirects to login when unauth", client.get("/"), 302)
check("GET /login is reachable", client.get("/login"))
check("GET /health open", client.get("/health"))
login()  # all further requests are authenticated

# --- Authenticated reads ---
check("GET / (authed)", client.get("/"))
check("GET /customers", client.get("/customers"))
check("GET /jobs", client.get("/jobs"))
check("GET /customers/new", client.get("/customers/new"))
check("GET /jobs/new", client.get("/jobs/new"))
check("GET /api/stats", client.get("/api/stats"))

# --- Create customer ---
r = client.post("/customers/new", data={
    "name": "Alice Auto", "phone": "555-1212", "email": "a@x.com",
    "address": "1 Main", "vehicle": "2017 Mazda", "notes": "ref Google"})
check("POST /customers/new", r, 302)
cid = models.customers_all()[-1]["id"]

# --- Edit customer ---
r = client.post(f"/customers/{cid}/edit", data={
    "name": "Alice Auto II", "phone": "555-9999", "email": "a2@x.com",
    "address": "2 Main", "vehicle": "2017 Mazda", "notes": "edit"})
check("POST /customers/{cid}/edit", r, 302)
assert models.customer_get(cid)["name"] == "Alice Auto II"

# --- Create job ---
r = client.post("/jobs/new", data={
    "customer_id": str(cid), "job_date": "2026-09-01",
    "service_type": "Premium", "status": "Completed",
    "price": "149", "cost": "20", "notes": "mobile"})
check("POST /jobs/new", r, 302)
jid = models.jobs_all()[-1]["id"]

# --- Edit job ---
r = client.post(f"/jobs/{jid}/edit", data={
    "customer_id": str(cid), "job_date": "2026-09-02",
    "service_type": "Premium+", "status": "Completed",
    "price": "159", "cost": "20", "notes": ""})
check("POST /jobs/{jid}/edit", r, 302)

# --- Add payment ---
r = client.post(f"/jobs/{jid}/pay", data={
    "amount": "100", "method": "Venmo", "pay_date": "2026-09-02", "note": "dep"})
check("POST /jobs/{jid}/pay", r, 302)
assert models.job_balance(jid) == 59.0, models.job_balance(jid)

# --- Detail pages ---
check("GET /customers/{cid}", client.get(f"/customers/{cid}"))
check("GET /jobs/{jid}", client.get(f"/jobs/{jid}"))

# --- Photos: upload before/after, serve, delete ---
import base64, io
_png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M8AAAMBAQDJ/pLvAAAAAElFTkSuQmCC")
r = client.post(f"/jobs/{jid}/photo/upload", data={
    "kind": "before",
    "photo": (io.BytesIO(_png), "before.png", "image/png"),
})
check("POST upload before-photo", r, 302)
r = client.post(f"/jobs/{jid}/photo/upload", data={
    "kind": "after",
    "photo": (io.BytesIO(_png), "after.png", "image/png"),
})
check("POST upload after-photo", r, 302)
ph = models.photos_for_job(jid)
assert len(ph) == 2, ph
assert {p["kind"] for p in ph} == {"before", "after"}
pid = ph[0]["id"]
r = client.get(f"/photo/{pid}")
check("GET /photo/<pid> serves image", r, 200)
assert r.content_type.startswith("image/"), r.content_type
assert r.data == _png
r = client.post(f"/photo/{pid}/delete")
check("POST delete photo", r, 302)
assert len(models.photos_for_job(jid)) == 1

# --- Delete payment ---
pid = models.payments_for_job(jid)[-1]["id"]
r = client.post(f"/jobs/{jid}/payment/{pid}/delete")
check("POST delete payment", r, 302)
assert models.job_balance(jid) == 159.0

# --- Delete job then customer (cascade) ---
r = client.post(f"/jobs/{jid}/delete")
check("POST delete job", r, 302)
r = client.post(f"/customers/{cid}/delete")
check("POST delete customer", r, 302)
assert models.customer_get(cid) is None

# --- Stats correctness on leftover demo data ---
s = models.dashboard_stats()
assert "revenue" in s and "profit" in s and "outstanding" in s
print(f"[OK] stats keys present: revenue={s['revenue']} profit={s['profit']}")

print("\n=== RESULT:", "ALL PASS" if not failures else f"{len(failures)} FAILURES ===")
for f in failures:
    print("  FAIL:", f)
raise SystemExit(1 if failures else 0)
