from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for
from pymongo.errors import DuplicateKeyError

from constants import AVAILABLE
from extensions import limiter
from models import inquiries, products
from services.auth import login_required
from services.validators import to_object_id, validate_message

inquiries_bp = Blueprint("inquiries", __name__)


@inquiries_bp.route("/products/<product_id>/inquire", methods=["POST"])
@login_required
@limiter.limit("20 per hour")
def inquire(product_id):
    pid = to_object_id(product_id)
    product = products.get_product(pid) if pid else None
    if product is None:
        abort(404)
    if product["seller_id"] == g.user["_id"]:
        abort(403)  # can't contact yourself
    back = redirect(url_for("products.detail", product_id=pid))
    if product["status"] != AVAILABLE:
        flash("This item has already been sold.", "error")
        return back
    message, error = validate_message(request.form)
    if error:
        flash(error, "error")
        return back
    try:
        inquiries.create(product, g.user["_id"], message)
    except DuplicateKeyError:
        flash("You have already contacted this seller about this item.", "error")
        return back
    flash("Message sent! The seller will see your name and contact details.", "success")
    return back


@inquiries_bp.route("/my/inquiries")
@login_required
def my_inquiries():
    return render_template("my_inquiries.html", received=inquiries.received(g.user["_id"]),
                           sent=inquiries.sent(g.user["_id"]))


@inquiries_bp.route("/inquiries/<inquiry_id>/reply", methods=["POST"])
@login_required
def reply(inquiry_id):
    iid = to_object_id(inquiry_id)
    inquiry = inquiries.get(iid) if iid else None
    if inquiry is None:
        abort(404)
    if inquiry["seller_id"] != g.user["_id"]:
        abort(403)
    text, error = validate_message(request.form, "reply", minimum=2)
    if error:
        flash(error, "error")
    else:
        inquiries.set_reply(iid, g.user["_id"], text, request.form.get("share_phone") == "on")
        flash("Reply sent.", "success")
    return redirect(url_for("inquiries.my_inquiries"))
