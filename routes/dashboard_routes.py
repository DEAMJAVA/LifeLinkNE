import io
import json
from collections import defaultdict

import qrcode
from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, g,
    send_file, abort,
)

from auth import login_required, health_worker_required, current_user
from data import (
    LOCATIONS, LOCATION_CHOICES, LOCATION_BY_LABEL, BLOOD_GROUPS,
    DISASTER_CATALOG, SEVERITY_COLORS, severity_for_disaster, severity_color,
    severity_weight, location_display_name, NE_INDIA_MAP_CENTER,
    NE_INDIA_MAP_DEFAULT_ZOOM,
)

bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")


def _can_manage(user, owner_id: str) -> bool:
    return bool(user.get("is_admin")) or user["user_id"] == owner_id


def _parse_latlon(location: str):
    try:
        lat_str, lon_str = (location or "").split(",")
        return float(lat_str.strip()), float(lon_str.strip())
    except (ValueError, AttributeError):
        return None


# ----------------------------------------------------------------------
# Disasters (live feed)
# ----------------------------------------------------------------------
@bp.route("/disasters")
@login_required
def disasters():
    user = current_user()
    rows = g.db.list_disasters()
    for r in rows:
        r["color"] = severity_color(r["severity"])
        r["location_label"] = location_display_name(r["location"])
        r["can_delete"] = _can_manage(user, r["reporter_id"])
    return render_template("partials/_disasters.html", disasters=rows)


@bp.route("/disasters/new", methods=["GET", "POST"])
@login_required
def report_disaster():
    user = current_user()
    if request.method == "POST":
        disaster = request.form.get("disaster", "").strip()
        severity = request.form.get("severity", "").strip()
        notes = request.form.get("notes", "").strip()
        lat = request.form.get("lat", "").strip()
        lon = request.form.get("lon", "").strip()

        if not disaster:
            flash("Please choose a disaster type.", "error")
            return render_template("partials/_report_disaster.html", catalog=DISASTER_CATALOG)

        # If the caller didn't pin a severity (or picked "All"), derive it
        # server-side from the catalog.
        if severity not in ("Severe", "Moderate", "Mild"):
            severity = severity_for_disaster(disaster)

        location = f"{lat}, {lon}" if lat and lon else user["exact_location"]

        g.db.report_disaster(
            reporter_id=user["user_id"],
            reporter_name=user["username"],
            location=location,
            disaster=disaster,
            severity=severity,
            notes=notes,
        )
        flash("Report submitted. Stay safe.", "success")
        return redirect(url_for("dashboard.disasters"))

    return render_template("partials/_report_disaster.html", catalog=DISASTER_CATALOG)


@bp.route("/disasters/<disaster_id>/delete", methods=["POST"])
@login_required
def delete_disaster(disaster_id):
    user = current_user()
    row = g.db.get_disaster(disaster_id)
    if not row:
        abort(404)
    if not _can_manage(user, row["reporter_id"]):
        abort(403)
    g.db.delete_disaster(disaster_id)
    flash("Report removed.", "success")
    return redirect(url_for("dashboard.disasters"))


@bp.route("/disasters/clear", methods=["POST"])
@login_required
def clear_disasters():
    user = current_user()
    if not user.get("is_admin"):
        abort(403)
    g.db.clear_disasters()
    flash("All disaster reports cleared.", "success")
    return redirect(url_for("dashboard.disasters"))


@bp.route("/disasters/map")
@login_required
def disaster_map():
    rows = g.db.list_disasters()

    heat_points = []
    for r in rows:
        latlon = _parse_latlon(r["location"])
        if latlon is None:
            continue
        heat_points.append([latlon[0], latlon[1], severity_weight(r["severity"])])

    by_location = defaultdict(lambda: {"count": 0, "max_severity": "Mild", "lat": None, "lon": None})
    severity_rank = {"Mild": 1, "Moderate": 2, "Severe": 3}
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

    return render_template(
        "partials/_disaster_map.html",
        heat_points_json=json.dumps(heat_points),
        hotspots=hotspots[:12],
        map_center=NE_INDIA_MAP_CENTER,
        map_zoom=NE_INDIA_MAP_DEFAULT_ZOOM,
        total_reports=len(rows),
    )


# ----------------------------------------------------------------------
# Blood donation network (no blood *requests* -- donors only)
# ----------------------------------------------------------------------
@bp.route("/blood/donations", methods=["GET", "POST"])
@login_required
def blood_donations():
    user = current_user()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        blood_type = request.form.get("blood_type", "").strip()
        contact = request.form.get("contact", "").strip()
        lat = request.form.get("lat", "").strip()
        lon = request.form.get("lon", "").strip()
        location = f"{lat}, {lon}" if lat and lon else user["exact_location"]

        if not (name and blood_type and contact):
            flash("Name, blood type, and contact are required.", "error")
        else:
            g.db.create_blood_donation(
                user_id=user["user_id"], name=name, location=location,
                blood_type=blood_type, contact=contact,
            )
            flash("Thank you for signing up to donate.", "success")
        return redirect(url_for("dashboard.blood_donations"))

    rows = g.db.list_blood_donations()
    for r in rows:
        r["location_label"] = location_display_name(r["location"])
        r["can_delete"] = _can_manage(user, r["user_id"])
    return render_template("partials/_blood_donations.html", donations=rows,
                            blood_groups=BLOOD_GROUPS)


@bp.route("/blood/donations/<row_id>/delete", methods=["POST"])
@login_required
def delete_blood_donation(row_id):
    user = current_user()
    row = g.db.get_blood_donation(row_id)
    if not row:
        abort(404)
    if not _can_manage(user, row["user_id"]):
        abort(403)
    g.db.delete_blood_donation(row_id)
    flash("Donor entry removed.", "success")
    return redirect(url_for("dashboard.blood_donations"))


@bp.route("/blood/donations/clear", methods=["POST"])
@login_required
def clear_blood_donations():
    user = current_user()
    if not user.get("is_admin"):
        abort(403)
    g.db.clear_blood_donations()
    flash("All donor entries cleared.", "success")
    return redirect(url_for("dashboard.blood_donations"))


# ----------------------------------------------------------------------
# Health worker: look up a person's health data by name
# ----------------------------------------------------------------------
@bp.route("/health-records")
@health_worker_required
def health_records():
    query = request.args.get("q", "").strip()
    results = g.db.search_users_by_name(query) if query else []
    return render_template("partials/_health_records.html", query=query, results=results)


# ----------------------------------------------------------------------
# Profile
# ----------------------------------------------------------------------
@bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user = current_user()

    if request.method == "POST":
        form = request.form
        first = form.get("first_name", "").strip()
        middle = form.get("middle_name", "").strip()
        last = form.get("last_name", "").strip()
        username = " ".join(p for p in (first, middle, last) if p)
        email = form.get("email", "").strip().lower()
        home_label = form.get("home_location", "")

        errors = []
        if not (first and email):
            errors.append("Name and email are required.")
        if home_label not in LOCATION_BY_LABEL:
            errors.append("Please choose a valid home location.")
        if g.db.email_taken(email, exclude_user_id=user["user_id"]):
            errors.append("That email is already in use by another account.")

        if errors:
            for e in errors:
                flash(e, "error")
            return redirect(url_for("dashboard.profile"))

        g.db.update_user(
            user["user_id"],
            username=username,
            email=email,
            birthday=form.get("birthday", "").strip(),
            disabilities=form.get("disabilities", "").strip(),
            home_location=LOCATION_BY_LABEL[home_label],
            blood_group=form.get("blood_group", "").strip(),
            diseases=form.get("diseases", "").strip(),
            allergies=form.get("allergies", "").strip(),
            important_contacts=form.get("important_contacts", "").strip(),
        )
        flash("Profile updated.", "success")
        return redirect(url_for("dashboard.profile"))

    name_parts = (user["username"] or "").split()
    first = name_parts[0] if name_parts else ""
    last = name_parts[-1] if len(name_parts) > 1 else ""
    middle = " ".join(name_parts[1:-1]) if len(name_parts) > 2 else ""
    current_home_label = next(
        (label for label, latlon in LOCATION_BY_LABEL.items()
         if latlon == user["home_location"]), ""
    )

    return render_template(
        "partials/_edit_user.html", user=user, first=first, middle=middle,
        last=last, locations=LOCATION_CHOICES, blood_groups=BLOOD_GROUPS,
        current_home_label=current_home_label,
    )


# ----------------------------------------------------------------------
# Emergency QR "health passport"
# ----------------------------------------------------------------------
@bp.route("/qr")
@login_required
def emergency_qr():
    user = current_user()
    lines = [
        f"Name: {user['username']}",
        f"Birthday: {user['birthday']}",
        f"Blood group: {user['blood_group']}",
        f"Disabilities: {user['disabilities'] or 'None'}",
        f"Diseases: {user['diseases'] or 'None'}",
        f"Allergies: {user['allergies'] or 'None'}",
        f"Emergency contacts: {user['important_contacts'] or 'None'}",
    ]
    payload = "\n".join(lines)

    img = qrcode.make(payload)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    return send_file(
        buf, mimetype="image/png", as_attachment=True,
        download_name="lifelinkne_health_passport.png",
    )
