"""
Local launcher for the Headlight CRM.

IMPORTANT: use this (waitress) instead of `python app.py`. On this machine the
Flask dev server's before_request hooks don't fire under `app.run()`, but they
work correctly under waitress — which is also what Render uses in production.

Run:  python run.py
Then open http://localhost:5000
"""
import os
import models
from app import app, resolve_password

models.init_db()
resolve_password()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    from waitress import serve
    print(f"\n  Headlight CRM running at http://localhost:{port}\n")
    serve(app, host="0.0.0.0", port=port)
