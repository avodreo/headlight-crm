"""
Headlight Restoration CRM — Flask application.
Server-rendered, mobile-responsive. Single-password auth (never open in prod).
"""
import os
import secrets
import time
from datetime import datetime, date

from flask import (
    Flask, request, redirect, url_for, render_template, session, flash, jsonify, g
)

import models

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
# Harden session cookies (safe for both http dev and https prod via proxy).
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("SECURE_COOKIES", "1") == "1",
)

PASSWORD = None  # resolved at startup in resolve_password()


def resolve_password():
    """Determine the app password.

    - If CRM_PASSWORD is set, use it (explicit choice wins).
    - Otherwise NEVER leave the app world-open: generate a strong password,
      persist it in the DB so it survives restarts (when the disk is attached),
      and print it to the startup logs.
    """
    global PASSWORD
    explicit = os.environ.get("CRM_PASSWORD", "").strip()
    if explicit:
        PASSWORD = explicit
        return
    stored = models.get_setting("admin_password")
    if stored:
        PASSWORD = stored
        return
    generated = secrets.token_urlsafe(12)
    try:
        models.set_setting("admin_password", generated)
    except Exception:
        pass  # if DB not writable yet, we'll just print it below
    PASSWORD = generated
    print("\n" + "=" * 60)
    print("  AUTO-GENERATED CRM PASSWORD (save this!):")
    print(f"     {generated}")
    print("  Set CRM_PASSWORD env var to choose your own and avoid regen.")
    print("=" * 60 + "\n")


# ----------------------------- Auth -----------------------------

# Brute-force protection: 5 failed attempts per IP, 1-minute lockout.
_LOGIN_ATTEMPTS = {}
_MAX_ATTEMPTS = 5
_LOCKOUT_SECONDS = 60


@app.before_request
def require_auth():
    # Health & static always open (health probes must work without auth).
    if request.endpoint in ("health", "static"):
        return
    if request.endpoint == "login":
        return
    if not session.get("authed"):
        return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        ip = request.remote_addr or "unknown"
        now = time.time()
        attempts, lock_until = _LOGIN_ATTEMPTS.get(ip, (0, 0))
        if now < lock_until:
            flash("Too many attempts. Try again in a minute.", "error")
            return render_template("login.html")
        if secrets.compare_digest(request.form.get("password", ""), PASSWORD or ""):
            _LOGIN_ATTEMPTS[ip] = (0, 0)
            session["authed"] = True
            session.permanent = True
            return redirect(url_for("dashboard"))
        attempts += 1
        if attempts >= _MAX_ATTEMPTS:
            _LOGIN_ATTEMPTS[ip] = (attempts, now + _LOCKOUT_SECONDS)
            flash("Too many attempts. Try again in a minute.", "error")
        else:
            _LOGIN_ATTEMPTS[ip] = (attempts, 0)
            flash("Incorrect password.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------------------- Helpers ----------------------------

def money(v):
    try:
        return f"${float(v):,.2f}"
    except (TypeError, ValueError):
        return "$0.00"


def today():
    return date.today().isoformat()


app.jinja_env.filters["money"] = money
app.jinja_env.globals["today"] = today
app.jinja_env.globals["now"] = datetime.now


# --------------------------- Dashboard ---------------------------

@app.route("/")
def dashboard():
    stats = models.dashboard_stats()
    return render_template("dashboard.html", stats=stats)


# --------------------------- Customers ---------------------------

@app.route("/customers")
def customers():
    rows = models.customers_all()
    return render_template("customers.html", customers=rows)


@app.route("/customers/new", methods=["GET", "POST"])
def customer_new():
    if request.method == "POST":
        cid = models.customer_create(
            name=request.form["name"].strip(),
            phone=request.form.get("phone", ""),
            email=request.form.get("email", ""),
            address=request.form.get("address", ""),
            vehicle=request.form.get("vehicle", ""),
            notes=request.form.get("notes", ""),
        )
        flash("Customer added.", "success")
        return redirect(url_for("customer_detail", cid=cid))
    return render_template("customer_form.html", customer=None, today=today())


@app.route("/customers/<int:cid>")
def customer_detail(cid):
    c = models.customer_get(cid)
    if not c:
        flash("Customer not found.", "error")
        return redirect(url_for("customers"))
    jobs = models.jobs_for_customer(cid)
    # attach balances
    for j in jobs:
        j["balance"] = models.job_balance(j["id"])
    return render_template("customer_detail.html", customer=c, jobs=jobs)


@app.route("/customers/<int:cid>/edit", methods=["GET", "POST"])
def customer_edit(cid):
    c = models.customer_get(cid)
    if not c:
        flash("Customer not found.", "error")
        return redirect(url_for("customers"))
    if request.method == "POST":
        models.customer_update(
            cid,
            name=request.form["name"].strip(),
            phone=request.form.get("phone", ""),
            email=request.form.get("email", ""),
            address=request.form.get("address", ""),
            vehicle=request.form.get("vehicle", ""),
            notes=request.form.get("notes", ""),
        )
        flash("Customer updated.", "success")
        return redirect(url_for("customer_detail", cid=cid))
    return render_template("customer_form.html", customer=c, today=today())


@app.route("/customers/<int:cid>/delete", methods=["POST"])
def customer_delete(cid):
    models.customer_delete(cid)
    flash("Customer deleted.", "success")
    return redirect(url_for("customers"))


# ------------------------------ Jobs ------------------------------

@app.route("/jobs")
def jobs():
    rows = models.jobs_all()
    for j in rows:
        j["balance"] = models.job_balance(j["id"])
    return render_template("jobs.html", jobs=rows)


@app.route("/jobs/new", methods=["GET", "POST"])
def job_new():
    customers = models.customers_all()
    if request.method == "POST":
        jid = models.job_create(
            customer_id=int(request.form["customer_id"]),
            job_date=request.form.get("job_date", "") or None,
            status=request.form.get("status", "Scheduled"),
            service_type=request.form.get("service_type", ""),
            price=float(request.form.get("price") or 0),
            cost=float(request.form.get("cost") or 0),
            notes=request.form.get("notes", ""),
        )
        flash("Job created.", "success")
        return redirect(url_for("job_detail", jid=jid))
    sel_cid = request.args.get("cid", type=int)
    return render_template("job_form.html", customers=customers, job=None,
                           sel_cid=sel_cid, today=today())


@app.route("/jobs/<int:jid>")
def job_detail(jid):
    j = models.job_get(jid)
    if not j:
        flash("Job not found.", "error")
        return redirect(url_for("jobs"))
    c = models.customer_get(j["customer_id"])
    payments = models.payments_for_job(jid)
    j["balance"] = models.job_balance(jid)
    return render_template("job_detail.html", job=j, customer=c, payments=payments)


@app.route("/jobs/<int:jid>/edit", methods=["GET", "POST"])
def job_edit(jid):
    j = models.job_get(jid)
    if not j:
        flash("Job not found.", "error")
        return redirect(url_for("jobs"))
    customers = models.customers_all()
    if request.method == "POST":
        models.job_update(
            jid,
            customer_id=int(request.form["customer_id"]),
            job_date=request.form.get("job_date", "") or None,
            status=request.form.get("status", "Scheduled"),
            service_type=request.form.get("service_type", ""),
            price=float(request.form.get("price") or 0),
            cost=float(request.form.get("cost") or 0),
            notes=request.form.get("notes", ""),
        )
        flash("Job updated.", "success")
        return redirect(url_for("job_detail", jid=jid))
    return render_template("job_form.html", customers=customers, job=j, today=today())


@app.route("/jobs/<int:jid>/delete", methods=["POST"])
def job_delete(jid):
    models.job_delete(jid)
    flash("Job deleted.", "success")
    return redirect(url_for("jobs"))


@app.route("/jobs/<int:jid>/pay", methods=["POST"])
def add_payment(jid):
    amount = float(request.form.get("amount") or 0)
    method = request.form.get("method", "")
    pay_date = request.form.get("pay_date", "") or today()
    note = request.form.get("note", "")
    models.payment_create(jid, amount, method, pay_date, note)
    flash("Payment recorded.", "success")
    return redirect(url_for("job_detail", jid=jid))


@app.route("/jobs/<int:jid>/payment/<int:pid>/delete", methods=["POST"])
def delete_payment(jid, pid):
    models.payment_delete(pid)
    flash("Payment removed.", "success")
    return redirect(url_for("job_detail", jid=jid))


# ------------------------------ API ------------------------------

@app.route("/api/stats")
def api_stats():
    if not session.get("authed"):
        return jsonify({"error": "unauthorized"}), 401
    return jsonify(models.dashboard_stats())


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


# -----------------------------------------------------------------

if __name__ == "__main__":
    models.init_db()
    resolve_password()
    # Loud warning: on Render (and most PaaS), the filesystem is ephemeral.
    # Without a persistent disk + CRM_DB_PATH, the database is wiped on restart.
    on_paas = bool(os.environ.get("RENDER")) or os.environ.get("PORT") and os.path.exists("/.dockerenv")
    if on_paas and not os.environ.get("CRM_DB_PATH"):
        print("\n" + "!" * 60)
        print("  WARNING: no CRM_DB_PATH set on a PaaS host.")
        print("  Your data will be LOST on every restart/deploy.")
        print("  Attach a persistent disk and set CRM_DB_PATH=/var/data/crm.db")
        print("!" * 60 + "\n")
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
