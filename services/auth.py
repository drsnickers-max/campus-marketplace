import functools
from urllib.parse import urlparse

import bcrypt
from flask import current_app, flash, g, redirect, request, url_for

_DUMMY_HASH = bcrypt.hashpw(b"dummy-password", bcrypt.gensalt(rounds=10))


def hash_password(password):
    rounds = current_app.config.get("BCRYPT_ROUNDS", 12)
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=rounds))


def verify_password(password, hashed):
    try:
        return bcrypt.checkpw(password.encode("utf-8")[:72], hashed)
    except (ValueError, TypeError):
        return False


def waste_time(password):
    """Run a hash check for unknown emails so response time doesn't reveal if an account exists."""
    bcrypt.checkpw(password.encode("utf-8")[:72], _DUMMY_HASH)


def login_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            flash("Please log in to continue.", "error")
            target = request.full_path.rstrip("?") if request.method == "GET" else None
            return redirect(url_for("auth.login", next=target))
        return view(*args, **kwargs)
    return wrapped


def safe_next(target):
    """Only allow redirects to paths on this site (prevents open-redirect attacks)."""
    if not target:
        return None
    parsed = urlparse(target)
    if parsed.scheme or parsed.netloc or not target.startswith("/") or target.startswith("//"):
        return None
    return target
