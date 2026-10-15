import logging

from flask import (Blueprint, current_app, flash, g, redirect, render_template,
                   request, session, url_for)
from pymongo.errors import DuplicateKeyError

from extensions import limiter
from models import users
from services.auth import hash_password, safe_next, verify_password, waste_time
from services.validators import validate_registration

auth_bp = Blueprint("auth", __name__)
logger = logging.getLogger(__name__)


@auth_bp.route("/register", methods=["GET", "POST"])
@limiter.limit("10 per hour", methods=["POST"])
def register():
    if g.user:
        return redirect(url_for("main.index"))
    errors, form = {}, {}
    if request.method == "POST":
        form = request.form
        clean, errors = validate_registration(form, current_app.config["ALLOWED_EMAIL_DOMAINS"])
        if not errors:
            try:
                users.create_user({**clean, "password_hash": hash_password(form["password"])})
            except DuplicateKeyError:
                errors["form"] = "An account with that email or registration number already exists."
            else:
                logger.info("New user registered")
                flash("Account created. Please log in.", "success")
                return redirect(url_for("auth.login"))
        return render_template("register.html", errors=errors, form=form), 400
    return render_template("register.html", errors=errors, form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def login():
    if g.user:
        return redirect(url_for("main.index"))
    if request.method == "POST":
        email = str(request.form.get("email", "")).strip().lower()  # always a plain string
        password = str(request.form.get("password", ""))
        user = users.get_by_email(email)
        if user and verify_password(password, user["password_hash"]):
            session.clear()  # new session on login (prevents session fixation)
            session["user_id"] = str(user["_id"])
            session.permanent = True
            return redirect(safe_next(request.args.get("next")) or url_for("main.index"))
        if not user:
            waste_time(password)
        logger.info("Failed login attempt")  # no email/password in logs
        return render_template("login.html", error="Invalid email or password."), 401
    return render_template("login.html", error=None)


@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("main.index"))
