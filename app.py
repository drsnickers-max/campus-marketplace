import logging
import os

from flask import Flask, g, redirect, render_template, request, session, url_for

from config import Config
from db import init_db
from extensions import csrf, limiter
from models import users
from services.images import configure_cloudinary

ERROR_TEXT = {
    400: ("Bad request", "Something was wrong with that request (your form may have expired). Please go back and try again."),
    403: ("Not allowed", "You don't have permission to do that."),
    404: ("Not found", "We couldn't find that page."),
    405: ("Method not allowed", "That action isn't supported here."),
    413: ("Upload too large", "The files you sent are too large."),
    429: ("Slow down", "Too many attempts. Please wait a bit and try again."),
    500: ("Something went wrong", "An unexpected error occurred. Please try again later."),
}
PUBLIC_ENDPOINTS = {"auth.login", "auth.register", "main.health", "static"}


def create_app(test_config=None, mongo_client=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if app.config["SECRET_KEY"] == "dev-only-insecure-key" and not app.testing:
        app.logger.warning("SECRET_KEY is the insecure default. Set a real one in .env.")

    init_db(app, client=mongo_client)
    csrf.init_app(app)
    limiter.init_app(app)
    configure_cloudinary(app)

    from routes.auth import auth_bp
    from routes.inquiries import inquiries_bp
    from routes.main import main_bp
    from routes.products import products_bp
    from routes.profile import profile_bp
    from routes.reviews import reviews_bp
    for bp in (main_bp, auth_bp, products_bp, profile_bp, inquiries_bp, reviews_bp):
        app.register_blueprint(bp)

    @app.before_request
    def load_user():
        g.user = None
        uid = session.get("user_id")
        if uid:
            g.user = users.get_by_id(uid)
            if g.user is None:
                session.clear()
        if (app.config["REQUIRE_LOGIN_TO_BROWSE"] and g.user is None
                and request.endpoint not in PUBLIC_ENDPOINTS):
            return redirect(url_for("auth.login"))

    @app.after_request
    def security_headers(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "same-origin"
        resp.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' https://res.cloudinary.com data: blob:; "
            "style-src 'self'; script-src 'self'; form-action 'self'; frame-ancestors 'none'")
        return resp

    @app.template_filter("inr")
    def inr(value):
        return f"₹{int(value):,}"

    @app.template_filter("date")
    def date(value):
        return value.strftime("%d %b %Y") if value else ""

    def handle(error):
        code = getattr(error, "code", 500) or 500
        title, message = ERROR_TEXT.get(code, ERROR_TEXT[500])
        return render_template("error.html", code=code, title=title, message=message), code

    for code in ERROR_TEXT:
        app.register_error_handler(code, handle)
    return app


if __name__ == "__main__":
    create_app().run(debug=os.environ.get("FLASK_DEBUG") == "1")
