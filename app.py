"""
Headlight Restoration CRM — Flask application.
Server-rendered, mobile-responsive. Optional single-password auth.
"""
import os
from datetime import datetime, date

from flask import (
    Flask, request, redirect, url_for, render_template, session, flash, jsonify, g
)

import models

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-change-me-in-production")

PASSWORD = os.environ.get("CRM_PASSWORD", "")  # empty = open access


# ----------------------------- Auth -----------------------------

@app.before_request
def require_auth():
    if not PASSWORD:
        return
    # Allow the login route and static assets always.
    if request.endpoint in ("login", "static"):
        return
    if not session.get("authed"):
        return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if not PASSWORD:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        if request.form.get("password", "") == PASSWORD:
            session["authed"] = True
            return redirect(url_for("dashboard"))
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
    if PASSWORD and not session.get("authed"):
        return jsonify({"error": "unauthorized"}), 401
    return jsonify(models.dashboard_stats())


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


# -----------------------------------------------------------------

if __name__ == "__main__":
    models.init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
