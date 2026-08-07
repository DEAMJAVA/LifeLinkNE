from flask import Blueprint, request, jsonify, g, send_file
import io
import qrcode
from collections import defaultdict

from auth import (
    hash_password, verify_password, password_is_strong,
    current_api_user, api_login_required, api_admin_required,
    api_health_worker_required, get_bearer_token,
)
from data import (
    LOCATIONS, LOCATION_CHOICES, LOCATION_BY_LABEL, BLOOD_GROUPS,
    DISASTER_CATALOG, NE_STATES, severity_for_disaster, severity_color,
    severity_weight, location_display_name, NE_INDIA_MAP_CENTER,
    NE_INDIA_MAP_DEFAULT_ZOOM,
)

bp = Blueprint("api", __name__, url_prefix="/api/v1")


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def _parse_latlon(location: str):
    try:
        lat_str, lon_str = (location or "").split(",")
        return float(lat_str.strip()), float(lon_str.strip())
    except (ValueError, AttributeError):
        return None


def _location_obj(latlon: str):
    if not latlon:
        return None
    parsed = _parse_latlon(latlon)
    return {
        "raw": latlon,
        "lat": parsed[0] if parsed else None,
        "lon": parsed[1] if parsed else None,
        "label": location_display_name(latlon),
    }


def _public_user(u: dict) -> dict:
    return {
        "user_id": u["user_id"],
        "username": u.get("username", ""),
        "email": u.get("email", ""),
        "birthday": u.get("birthday", ""),
        "disabilities": u.get("disabilities", ""),
        "home_location": _location_obj(u.get("home_location")),
        "exact_location": _location_obj(u.get("exact_location")),
        "is_admin": bool(u.get("is_admin")),
        "is_health_worker": bool(u.get("is_health_worker")),
        "blood_group": u.get("blood_group", ""),
        "diseases": u.get("diseases", ""),
        "allergies": u.get("allergies", ""),
        "important_contacts": u.get("important_contacts", ""),
        "created_at": u.get("created_at", ""),
    }


def _health_record(u: dict) -> dict:
    """Narrower payload for the health-worker lookup endpoint -- no email,
    no password hash, no admin/location metadata, just the health fields."""
    return {
        "user_id": u["user_id"],
        "username": u.get("username", ""),
        "birthday": u.get("birthday", ""),
        "blood_group": u.get("blood_group", ""),
        "disabilities": u.get("disabilities", ""),
        "diseases": u.get("diseases", ""),
        "allergies": u.get("allergies", ""),
        "important_contacts": u.get("important_contacts", ""),
    }


def _public_disaster(d: dict, viewer: dict) -> dict:
    return {
        "disaster_id": d["disaster_id"],
        "reporter_name": d.get("reporter_name", ""),
        "location": _location_obj(d.get("location")),
        "disaster": d.get("disaster", ""),
        "severity": d.get("severity", "Mild"),
        "severity_color": severity_color(d.get("severity", "Mild")),
        "notes": d.get("notes", ""),
        "reported_at": d.get("reported_at", ""),
        "can_delete": bool(viewer.get("is_admin")) or viewer["user_id"] == d.get("reporter_id"),
    }


def _public_donation(don: dict, viewer: dict) -> dict:
    return {
        "id": don["id"],
        "name": don.get("name", ""),
        "location": _location_obj(don.get("location")),
        "blood_type": don.get("blood_type", ""),
        "contact": don.get("contact", ""),
        "created_at": don.get("created_at", ""),
        "can_delete": bool(viewer.get("is_admin")) or viewer["user_id"] == don.get("user_id"),
    }


def _can_manage(user, owner_id: str) -> bool:
    return bool(user.get("is_admin")) or user["user_id"] == owner_id


# ------------------------------------------------------------------
# Reference data
# ------------------------------------------------------------------
@bp.route("/meta")
def meta():
    return jsonify({
        "ne_states": NE_STATES,
        "locations": [
            {"label": label, "lat": _parse_latlon(latlon)[0], "lon": _parse_latlon(latlon)[1]}
            for label, latlon in LOCATION_BY_LABEL.items()
        ],
        "blood_groups": BLOOD_GROUPS,
        "disaster_catalog": DISASTER_CATALOG,
        "map_center": {"lat": NE_INDIA_MAP_CENTER[0], "lon": NE_INDIA_MAP_CENTER[1]},
        "map_default_zoom": NE_INDIA_MAP_DEFAULT_ZOOM,
    })


# ------------------------------------------------------------------
# Auth
# ------------------------------------------------------------------
@bp.route("/auth/register", methods=["POST"])
def register():
    body = request.get_json(silent=True) or {}

    username = (body.get("username") or "").strip()
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    birthday = (body.get("birthday") or "").strip()
    disabilities = (body.get("disabilities") or "").strip()
    home_label = body.get("home_location") or ""
    exact_location = (body.get("exact_location") or "").strip()
    blood_group = (body.get("blood_group") or "").strip()
    diseases = (body.get("diseases") or "").strip()
    allergies = (body.get("allergies") or "").strip()
    important_contacts = (body.get("important_contacts") or "").strip()

    errors = []
    if not (username and email and password):
        errors.append("username, email, and password are required.")
    if not password_is_strong(password):
        errors.append("Password must be at least 8 characters and include a digit and a symbol (!@#$%^&*).")
    if home_label not in LOCATION_BY_LABEL:
        errors.append("home_location must be one of the values from GET /api/v1/meta.")
    if not exact_location:
        exact_location = LOCATION_BY_LABEL.get(home_label, "")
    if email and g.db.email_taken(email):
        errors.append("An account with that email already exists.")

    if errors:
        return jsonify({"errors": errors}), 400

    # Registration only ever creates a regular account -- admin and health
    # worker roles are granted out-of-band (see make_admin.py /
    # make_health_worker.py), never via self-service signup.
    user_id = g.db.create_user(
        username=username,
        email=email,
        password_hash=hash_password(password),
        birthday=birthday,
        disabilities=disabilities,
        home_location=LOCATION_BY_LABEL[home_label],
        exact_location=exact_location,
        blood_group=blood_group,
        diseases=diseases,
        allergies=allergies,
        important_contacts=important_contacts,
    )
    token = g.db.create_api_token(user_id)
    user = g.db.get_user_by_id(user_id)
    return jsonify({"token": token, "user": _public_user(user)}), 201


@bp.route("/auth/login", methods=["POST"])
def login():
    body = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""

    user = g.db.get_user_by_email(email) if email else None
    if not user or not verify_password(password, user["password_hash"]):
        return jsonify({"error": "Incorrect email or password."}), 401

    token = g.db.create_api_token(user["user_id"])
    return jsonify({"token": token, "user": _public_user(user)})


@bp.route("/auth/logout", methods=["POST"])
@api_login_required
def logout():
    token = get_bearer_token()
    if token:
        g.db.delete_api_token(token)
    return "", 204


@bp.route("/auth/logout-all", methods=["POST"])
@api_login_required
def logout_all():
    user = current_api_user()
    g.db.delete_all_tokens_for_user(user["user_id"])
    return "", 204


# ------------------------------------------------------------------
# Profile
# ------------------------------------------------------------------
@bp.route("/me", methods=["GET"])
@api_login_required
def get_me():
    return jsonify(_public_user(current_api_user()))


@bp.route("/me", methods=["PATCH"])
@api_login_required
def update_me():
    user = current_api_user()
    body = request.get_json(silent=True) or {}
    fields = {}

    if "username" in body:
        fields["username"] = (body["username"] or "").strip()
    if "email" in body:
        new_email = (body["email"] or "").strip().lower()
        if g.db.email_taken(new_email, exclude_user_id=user["user_id"]):
            return jsonify({"errors": ["That email is already in use by another account."]}), 400
        fields["email"] = new_email
    if "birthday" in body:
        fields["birthday"] = (body["birthday"] or "").strip()
    if "disabilities" in body:
        fields["disabilities"] = (body["disabilities"] or "").strip()
    if "home_location" in body:
        if body["home_location"] not in LOCATION_BY_LABEL:
            return jsonify({"errors": ["home_location must be one of the values from GET /api/v1/meta."]}), 400
        fields["home_location"] = LOCATION_BY_LABEL[body["home_location"]]
    if "blood_group" in body:
        fields["blood_group"] = (body["blood_group"] or "").strip()
    if "diseases" in body:
        fields["diseases"] = (body["diseases"] or "").strip()
    if "allergies" in body:
        fields["allergies"] = (body["allergies"] or "").strip()
    if "important_contacts" in body:
        fields["important_contacts"] = (body["important_contacts"] or "").strip()

    if fields:
        g.db.update_user(user["user_id"], **fields)

    return jsonify(_public_user(g.db.get_user_by_id(user["user_id"])))


# ------------------------------------------------------------------
# Disaster reports
# ------------------------------------------------------------------
@bp.route("/disasters", methods=["GET"])
@api_login_required
def list_disasters():
    user = current_api_user()
    rows = g.db.list_disasters()
    return jsonify({"disasters": [_public_disaster(d, user) for d in rows]})


@bp.route("/disasters", methods=["POST"])
@api_login_required
def create_disaster():
    user = current_api_user()
    body = request.get_json(silent=True) or {}

    disaster = (body.get("disaster") or "").strip()
    severity = (body.get("severity") or "").strip()
    notes = (body.get("notes") or "").strip()
    lat = body.get("lat")
    lon = body.get("lon")

    if not disaster:
        return jsonify({"errors": ["disaster is required. See GET /api/v1/meta for the catalog."]}), 400

    if severity not in ("Severe", "Moderate", "Mild"):
        severity = severity_for_disaster(disaster)

    if lat is not None and lon is not None:
        location = f"{lat}, {lon}"
    else:
        location = user["exact_location"]

    disaster_id = g.db.report_disaster(
        reporter_id=user["user_id"],
        reporter_name=user["username"],
        location=location,
        disaster=disaster,
        severity=severity,
        notes=notes,
    )
    return jsonify(_public_disaster(g.db.get_disaster(disaster_id), user)), 201


@bp.route("/disasters/<disaster_id>", methods=["DELETE"])
@api_login_required
def delete_disaster(disaster_id):
    user = current_api_user()
    row = g.db.get_disaster(disaster_id)
    if not row:
        return jsonify({"error": "Not found."}), 404
    if not _can_manage(user, row["reporter_id"]):
        return jsonify({"error": "Not allowed."}), 403
    g.db.delete_disaster(disaster_id)
    return "", 204


@bp.route("/disasters/clear", methods=["POST"])
@api_admin_required
def clear_disasters():
    g.db.clear_disasters()
    return "", 204


# ------------------------------------------------------------------
# Disaster intensity map (heatmap data)
# ------------------------------------------------------------------
@bp.route("/disasters/map", methods=["GET"])
@api_login_required
def disaster_map():
    rows = g.db.list_disasters()

    heat_points = []
    for r in rows:
        latlon = _parse_latlon(r["location"])
        if latlon is None:
            continue
        heat_points.append([latlon[0], latlon[1], severity_weight(r["severity"])])

    severity_rank = {"Mild": 1, "Moderate": 2, "Severe": 3}
    by_location = defaultdict(lambda: {"count": 0, "max_severity": "Mild", "lat": None, "lon": None})
    for r in rows:
        latlon = _parse_latlon(r["location"])
        if latlon is None:
            continue
        entry = by_location[r["location"]]
        entry["count"] += 1
        entry["lat"], entry["lon"] = latlon
        if severity_rank.get(r["severity"], 1) > severity_rank.get(entry["max_severity"], 1):
            entry["max_severity"] = r["severity"]
        entry["label"] = location_display_name(r["location"])

    hotspots = sorted(by_location.values(), key=lambda e: e["count"], reverse=True)
    for h in hotspots:
        h["color"] = severity_color(h["max_severity"])

    return jsonify({
        "heat_points": heat_points,
        "hotspots": hotspots[:20],
        "total_reports": len(rows),
        "map_center": {"lat": NE_INDIA_MAP_CENTER[0], "lon": NE_INDIA_MAP_CENTER[1]},
        "map_default_zoom": NE_INDIA_MAP_DEFAULT_ZOOM,
    })


# ------------------------------------------------------------------
# Blood donation network (donors only -- no blood *request* endpoints)
# ------------------------------------------------------------------
@bp.route("/blood/donations", methods=["GET"])
@api_login_required
def list_blood_donations():
    user = current_api_user()
    rows = g.db.list_blood_donations()
    return jsonify({"donations": [_public_donation(d, user) for d in rows]})


@bp.route("/blood/donations", methods=["POST"])
@api_login_required
def create_blood_donation():
    user = current_api_user()
    body = request.get_json(silent=True) or {}

    name = (body.get("name") or "").strip()
    blood_type = (body.get("blood_type") or "").strip()
    contact = (body.get("contact") or "").strip()
    lat = body.get("lat")
    lon = body.get("lon")

    if not (name and blood_type and contact):
        return jsonify({"errors": ["name, blood_type, and contact are required."]}), 400

    location = f"{lat}, {lon}" if (lat is not None and lon is not None) else user["exact_location"]

    row_id = g.db.create_blood_donation(
        user_id=user["user_id"], name=name, location=location,
        blood_type=blood_type, contact=contact,
    )
    return jsonify(_public_donation(g.db.get_blood_donation(row_id), user)), 201


@bp.route("/blood/donations/<row_id>", methods=["DELETE"])
@api_login_required
def delete_blood_donation(row_id):
    user = current_api_user()
    row = g.db.get_blood_donation(row_id)
    if not row:
        return jsonify({"error": "Not found."}), 404
    if not _can_manage(user, row["user_id"]):
        return jsonify({"error": "Not allowed."}), 403
    g.db.delete_blood_donation(row_id)
    return "", 204


@bp.route("/blood/donations/clear", methods=["POST"])
@api_admin_required
def clear_blood_donations():
    g.db.clear_blood_donations()
    return "", 204


# ------------------------------------------------------------------
# Health worker: record lookup by name
# ------------------------------------------------------------------
@bp.route("/health-records", methods=["GET"])
@api_health_worker_required
def health_records():
    query = request.args.get("q", "")
    rows = g.db.search_users_by_name(query) if query.strip() else []
    return jsonify({"results": [_health_record(u) for u in rows]})


# ------------------------------------------------------------------
# Emergency QR / health passport
# ------------------------------------------------------------------
@bp.route("/me/passport", methods=["GET"])
@api_login_required
def passport_payload():
    """Plain-text payload for clients that want to render the QR code
    themselves (sharper on high-DPI screens than a downloaded PNG)."""
    user = current_api_user()
    lines = [
        f"Name: {user['username']}",
        f"Birthday: {user['birthday']}",
        f"Blood group: {user['blood_group']}",
        f"Disabilities: {user['disabilities'] or 'None'}",
        f"Diseases: {user['diseases'] or 'None'}",
        f"Allergies: {user['allergies'] or 'None'}",
        f"Emergency contacts: {user['important_contacts'] or 'None'}",
    ]
    return jsonify({"payload": "\n".join(lines)})


@bp.route("/me/qr", methods=["GET"])
@api_login_required
def qr_png():
    """Same PNG the web app downloads, for clients that would rather
    just display an image than generate their own QR code."""
    user = current_api_user()
    lines = [
        f"Name: {user['username']}",
        f"Birthday: {user['birthday']}",
        f"Blood group: {user['blood_group']}",
        f"Disabilities: {user['disabilities'] or 'None'}",
        f"Diseases: {user['diseases'] or 'None'}",
        f"Allergies: {user['allergies'] or 'None'}",
        f"Emergency contacts: {user['important_contacts'] or 'None'}",
    ]
    img = qrcode.make("\n".join(lines))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")


# ------------------------------------------------------------------
# JSON error handlers -- so 404/405 on an /api/v1/... path returns
# JSON instead of the HTML error page the rest of the app uses.
# ------------------------------------------------------------------
@bp.errorhandler(404)
def api_not_found(e):
    return jsonify({"error": "Not found."}), 404


@bp.errorhandler(405)
def api_method_not_allowed(e):
    return jsonify({"error": "Method not allowed."}), 405
