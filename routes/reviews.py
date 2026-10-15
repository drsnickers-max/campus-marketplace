from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for
from pymongo.errors import DuplicateKeyError

from models import reviews, transactions
from services.auth import login_required
from services.validators import to_object_id, validate_review

reviews_bp = Blueprint("reviews", __name__)


@reviews_bp.route("/my/purchases")
@login_required
def my_purchases():
    return render_template("my_purchases.html", items=transactions.purchases_for_buyer(g.user["_id"]))


@reviews_bp.route("/transactions/<transaction_id>/review", methods=["POST"])
@login_required
def create_review(transaction_id):
    tid = to_object_id(transaction_id)
    tx = transactions.get(tid) if tid else None
    if tx is None:
        abort(404)
    # Eligibility: only the buyer of a COMPLETED sale, never the seller themselves
    if tx.get("buyer_id") != g.user["_id"] or tx["seller_id"] == g.user["_id"] or tx["status"] != "COMPLETED":
        abort(403)
    clean, errors = validate_review(request.form)
    if errors:
        flash(" ".join(errors.values()), "error")
        return redirect(url_for("reviews.my_purchases"))
    try:
        reviews.create(tx, clean["rating"], clean["comment"])  # unique index blocks duplicates
    except DuplicateKeyError:
        flash("You have already reviewed this purchase.", "error")
        return redirect(url_for("reviews.my_purchases"))
    reviews.recalculate_seller_rating(tx["seller_id"])
    flash("Thanks for your review!", "success")
    return redirect(url_for("reviews.my_purchases"))
