import re
from functools import wraps

from flask import session, redirect, url_for, flash, g, abort, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

PASSWORD_RE = re.compile(r"^(?=.*\d)(?=.*[!@#$%^&*]).{8,}$")


def hash_password(password: str) -> str:
    return generate_password_hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return check_password_hash(password_hash, password)


def password_is_strong(password: str) -> bool:
    return bool(PASSWORD_RE.match(password or ""))


def log_in_user(user_id: str):
    session.clear()
    session["user_id"] = user_id
    session.permanent = True


def log_out_user():
    session.clear()


def current_user():
    if "user" in g:
        return g.user
    user_id = session.get("user_id")
    g.user = g.db.get_user_by_id(user_id) if user_id else None
    return g.user


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_user() is None:
            flash("Please log in to continue.", "error")
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if user is None:
            flash("Please log in to continue.", "error")
            return redirect(url_for("auth.login"))
        if not user.get("is_admin"):
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def health_worker_required(view):
    """Gate for the health-worker record lookup tab. Admins can also see
    it, since they already have full access to everything else."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if user is None:
            flash("Please log in to continue.", "error")
            return redirect(url_for("auth.login"))
        if not (user.get("is_health_worker") or user.get("is_admin")):
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def _bearer_token_from_request() -> str | None:
    header = request.headers.get("Authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return None


get_bearer_token = _bearer_token_from_request


def current_api_user():
    if "api_user" in g:
        return g.api_user
    token = _bearer_token_from_request()
    g.api_user = g.db.get_user_by_token(token) if token else None
    return g.api_user


def api_login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_api_user() is None:
            return jsonify({"error": "Missing or invalid API token."}), 401
        return view(*args, **kwargs)
    return wrapped


def api_admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_api_user()
        if user is None:
            return jsonify({"error": "Missing or invalid API token."}), 401
        if not user.get("is_admin"):
            return jsonify({"error": "Admin privileges required."}), 403
        return view(*args, **kwargs)
    return wrapped


def api_health_worker_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_api_user()
        if user is None:
            return jsonify({"error": "Missing or invalid API token."}), 401
        if not (user.get("is_health_worker") or user.get("is_admin")):
            return jsonify({"error": "Health worker privileges required."}), 403
        return view(*args, **kwargs)
    return wrapped
