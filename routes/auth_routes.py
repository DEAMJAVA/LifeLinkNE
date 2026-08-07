from flask import Blueprint, render_template, request, redirect, url_for, flash, g

from auth import (
    hash_password, verify_password, password_is_strong,
    log_in_user, log_out_user, current_user,
)
from data import LOCATIONS, LOCATION_CHOICES, LOCATION_BY_LABEL, BLOOD_GROUPS

bp = Blueprint("auth", __name__)


@bp.route("/")
def start():
    if current_user():
        return redirect(url_for("dashboard.disasters"))
    return render_template("start.html")


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user():
        return redirect(url_for("dashboard.disasters"))

    if request.method == "POST":
        form = request.form
        first = form.get("first_name", "").strip()
        middle = form.get("middle_name", "").strip()
        last = form.get("last_name", "").strip()
        username = " ".join(p for p in (first, middle, last) if p)
        email = form.get("email", "").strip().lower()
        password = form.get("password", "")
        confirm = form.get("confirm_password", "")
        birthday = form.get("birthday", "").strip()
        disabilities = form.get("disabilities", "").strip()
        home_label = form.get("home_location", "")
        exact_location = form.get("exact_location", "").strip()
        blood_group = form.get("blood_group", "").strip()
        diseases = form.get("diseases", "").strip()
        allergies = form.get("allergies", "").strip()
        important_contacts = form.get("important_contacts", "").strip()

        errors = []
        if not (first and email and password):
            errors.append("Name, email, and password are required.")
        if password != confirm:
            errors.append("Passwords do not match.")
        if not password_is_strong(password):
            errors.append("Password must be at least 8 characters and include a digit and a symbol (!@#$%^&*).")
        if home_label not in LOCATION_BY_LABEL:
            errors.append("Please choose a valid home location.")
        if not exact_location:
            # Live GPS capture failed/was blocked -- fall back to the chosen
            # home location instead of hard-failing registration.
            exact_location = LOCATION_BY_LABEL.get(home_label, "")
        if g.db.email_taken(email):
            errors.append("An account with that email already exists.")

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template(
                "register.html", locations=LOCATION_CHOICES,
                blood_groups=BLOOD_GROUPS, form=form,
            )

        g.db.create_user(
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
        flash("Account created. Please log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("register.html", locations=LOCATION_CHOICES,
                            blood_groups=BLOOD_GROUPS, form={})


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user():
        return redirect(url_for("dashboard.disasters"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = g.db.get_user_by_email(email) if email else None
        if not user or not verify_password(password, user["password_hash"]):
            flash("Incorrect email or password.", "error")
            return render_template("login.html", email=email)

        log_in_user(user["user_id"])
        return redirect(url_for("dashboard.disasters"))

    return render_template("login.html", email="")


@bp.route("/logout")
def logout():
    log_out_user()
    flash("You've been logged out.", "success")
    return redirect(url_for("auth.start"))
