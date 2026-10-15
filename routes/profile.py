from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from models import products, reviews, users
from services.auth import login_required
from services.images import ImageError, delete_images, save_image
from services.validators import to_object_id, validate_profile
from constants import AVAILABLE

profile_bp = Blueprint("profile", __name__)


@profile_bp.route("/profile")
@login_required
def me():
    return render_template("profile.html")


@profile_bp.route("/profile/edit", methods=["GET", "POST"])
@login_required
def edit():
    if request.method == "GET":
        return render_template("profile_edit.html", form=g.user, errors={})
    clean, errors = validate_profile(request.form)
    picture = request.files.get("profile_picture")
    new_pic = None
    if not errors and picture and picture.filename:
        try:
            new_pic = save_image(picture)
        except ImageError as exc:
            errors["profile_picture"] = str(exc)
    if errors:
        return render_template("profile_edit.html", form=request.form, errors=errors), 400
    if new_pic:
        clean["profile_picture"] = new_pic
    users.update_profile(g.user["_id"], clean)  # only whitelisted fields, never email/reg no.
    if new_pic and g.user.get("profile_picture"):
        delete_images([g.user["profile_picture"]])
    flash("Profile updated.", "success")
    return redirect(url_for("profile.me"))


@profile_bp.route("/sellers/<seller_id>")
def seller(seller_id):
    """Public profile: name, year, rating, reviews and listings. No phone/email/reg no."""
    sid = to_object_id(seller_id)
    user = users.public_view(users.get_by_id(sid)) if sid else None
    if user is None:
        abort(404)
    return render_template("seller_profile.html", seller=user,
                           reviews=reviews.for_seller(sid), listings=products.list_by_seller(sid, AVAILABLE))
