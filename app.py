from __future__ import annotations

import os
import sys

from flask import Flask, redirect, render_template, request, url_for

from config import CRYPTO_WALLETS, GITHUB_URL, OPERATOR
from search_service import search

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("TANGOWEB_SECRET", "tangoweb-local-dev")


@app.context_processor
def inject_site_config():
    dark_mode = request.cookies.get("dark_mode", "false") == "true"
    return {"github_url": GITHUB_URL, "operator": OPERATOR, "dark_mode": dark_mode}

REGIONS = {
    "us-en": "United States",
    "uk-en": "United Kingdom",
    "de-de": "Germany",
    "fr-fr": "France",
    "es-es": "Spain",
    "it-it": "Italy",
    "nl-nl": "Netherlands",
    "au-en": "Australia",
    "ca-en": "Canada",
    "wt-wt": "Worldwide",
}

SAFESEARCH_OPTIONS = ("off", "moderate", "on")


@app.after_request
def privacy_headers(response):
    """Strip trackers by default — no referrer leakage, no third-party scripts."""
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Permissions-Policy"] = "interest-cohort=(), camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; "
        "style-src 'self'; "
        "img-src http: https: data: blob:; "
        "media-src http: https: data: blob:; "
        "video-src http: https: data: blob:; "
        "form-action 'self'; "
        "base-uri 'self'; "
        "frame-ancestors 'none'"
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/search")
def search_page():
    query = request.args.get("q", "").strip()
    tab = request.args.get("t", "all")
    page = request.args.get("p", 1, type=int)
    region = request.args.get("r", "us-en")
    safesearch = request.args.get("s", "off")

    if region not in REGIONS:
        region = "us-en"
    if safesearch not in SAFESEARCH_OPTIONS:
        safesearch = "off"

    if not query:
        return redirect(url_for("index"))

    results = search(query, tab=tab, page=page, region=region, safesearch=safesearch)

    return render_template(
        "results.html",
        results=results,
        regions=REGIONS,
        safesearch_options=SAFESEARCH_OPTIONS,
    )


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


@app.route("/donate")
def donate():
    wallets = {name: address for name, address in CRYPTO_WALLETS.items() if address}
    return render_template("donate.html", wallets=wallets)


@app.route("/toggle-dark-mode")
def toggle_dark_mode():
    """Toggle dark mode preference and redirect back to referrer."""
    current_dark_mode = request.cookies.get("dark_mode", "false") == "true"
    new_dark_mode = "false" if current_dark_mode else "true"
    redirect_to = request.referrer or url_for("index")
    response = redirect(redirect_to)
    response.set_cookie("dark_mode", new_dark_mode, max_age=31536000)  # 1 year
    return response


def _resolve_port() -> int:
    """Work out which port to run on: CLI arg > env var > interactive prompt > default."""
    if len(sys.argv) > 1:
        try:
            return int(sys.argv[1])
        except ValueError:
            print(f"Invalid port: {sys.argv[1]!r}. Falling back to other options.")
    env_port = os.environ.get("PORT")
    if env_port:
        try:
            return int(env_port)
        except ValueError:
            print(f"Invalid PORT env var: {env_port!r}. Falling back to other options.")
    if sys.stdin.isatty():
        raw = input("Enter port to run TangoWeb on [5000]: ").strip()
        if raw:
            try:
                return int(raw)
            except ValueError:
                print(f"Invalid port: {raw!r}. Using default port 5000.")
    return 5000

if __name__ == "__main__":
    port = _resolve_port()
    host = os.environ.get("HOST", "127.0.0.1")
    threads = int(os.environ.get("TANGOWEB_THREADS", 8))

    from waitress import serve

    print(f"TangoWeb running on http://{host}:{port} (waitress, {threads} threads)")
    serve(app, host=host, port=port, threads=threads)
