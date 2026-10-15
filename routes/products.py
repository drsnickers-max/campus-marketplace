import logging

from flask import Blueprint, abort, current_app, flash, g, redirect, render_template, request, url_for
from pymongo.errors import PyMongoError

from constants import AVAILABLE, CATEGORIES, CONDITIONS
from models import inquiries, products, transactions
from services.auth import login_required
from services.images import ImageError, delete_images, save_images
from services.validators import to_object_id, validate_product, validate_sale

products_bp = Blueprint("products", __name__)
logger = logging.getLogger(__name__)


def _owned_product_or_abort(product_id):
    """404 if missing, 403 if it's someone else's. Ownership is checked on every call."""
    pid = to_object_id(product_id)
    product = products.get_product(pid) if pid else None
    if product is None:
        abort(404)
    if product["seller_id"] != g.user["_id"]:
        abort(403)
    return product


def _uploaded_files():
    return [f for f in request.files.getlist("images") if f and f.filename]


def _form_page(**ctx):
    return render_template("product_form.html", categories=CATEGORIES, conditions=CONDITIONS, **ctx)


@products_bp.route("/products/new", methods=["GET", "POST"])
@login_required
def new():
    if request.method == "GET":
        return _form_page(form={}, errors={}, product=None)
    clean, errors = validate_product(request.form)
    files = _uploaded_files()
    images = []
    if not files:
        errors["images"] = "Add at least one image."
    elif len(files) > current_app.config["MAX_IMAGES"]:
        errors["images"] = f"You can upload at most {current_app.config['MAX_IMAGES']} images."
    if not errors:
        try:
            images = save_images(files)
        except ImageError as exc:
            errors["images"] = str(exc)
    if errors:
        return _form_page(form=request.form, errors=errors, product=None), 400
    pid = products.create_product({**clean, "images": images, "seller_id": g.user["_id"], "status": AVAILABLE})
    flash("Your listing is live!", "success")
    return redirect(url_for("products.detail", product_id=pid))


@products_bp.route("/products/<product_id>")
def detail(product_id):
    pid = to_object_id(product_id)
    product = products.get_with_seller(pid) if pid else None
    if product is None:
        abort(404)
    inquiry = None
    if g.user and g.user["_id"] != product["seller_id"]:
        inquiry = inquiries.get_for_buyer(pid, g.user["_id"])
    is_owner = bool(g.user and g.user["_id"] == product["seller_id"])
    return render_template("product_detail.html", p=product, inquiry=inquiry, is_owner=is_owner)


@products_bp.route("/products/<product_id>/edit", methods=["GET", "POST"])
@login_required
def edit(product_id):
    product = _owned_product_or_abort(product_id)
    if product["status"] != AVAILABLE:
        flash("Sold listings can't be edited.", "error")
        return redirect(url_for("products.detail", product_id=product["_id"]))
    if request.method == "GET":
        form = {**product, "price": str(product["price"])}
        return _form_page(form=form, errors={}, product=product)

    clean, errors = validate_product(request.form)
    drop = {int(i) for i in request.form.getlist("remove_images") if i.isdigit()}
    keep = [img for i, img in enumerate(product["images"]) if i not in drop]
    removed = [img for i, img in enumerate(product["images"]) if i in drop]
    files = _uploaded_files()
    total = len(keep) + len(files)
    if total < 1:
        errors["images"] = "A listing needs at least one image."
    elif total > current_app.config["MAX_IMAGES"]:
        errors["images"] = f"A listing can have at most {current_app.config['MAX_IMAGES']} images."
    new_images = []
    if not errors:
        try:
            new_images = save_images(files)
        except ImageError as exc:
            errors["images"] = str(exc)
    if errors:
        return _form_page(form=request.form, errors=errors, product=product), 400
    if products.update_product(product["_id"], g.user["_id"], {**clean, "images": keep + new_images}) == 0:
        delete_images(new_images)
        flash("This listing can no longer be edited.", "error")
        return redirect(url_for("products.my_listings"))
    delete_images(removed)
    flash("Listing updated.", "success")
    return redirect(url_for("products.detail", product_id=product["_id"]))


@products_bp.route("/products/<product_id>/sold", methods=["GET", "POST"])
@login_required
def mark_sold(product_id):
    """GET shows a confirmation page; POST performs the sale."""
    product = _owned_product_or_abort(product_id)
    if product["status"] != AVAILABLE:
        flash("This item is already marked as sold.", "error")
        return redirect(url_for("products.my_sold"))
    inquirers = inquiries.inquirers_for_product(product["_id"])
    if request.method == "POST":
        clean, errors = validate_sale(request.form, product["price"], {str(i["buyer_id"]) for i in inquirers})
        if not errors:
            sold = products.mark_sold(product["_id"], g.user["_id"])
            if sold is None:  # lost a race: someone (e.g. a double click) already did it
                flash("This item is already marked as sold.", "error")
                return redirect(url_for("products.my_sold"))
            try:
                transactions.create(sold, clean["buyer_id"], clean["price"])
            except PyMongoError:
                logger.exception("Could not record transaction for product %s", sold["_id"])
            flash("Marked as sold. Congratulations!", "success")
            return redirect(url_for("products.my_sold"))
        return render_template("mark_sold.html", p=product, inquirers=inquirers,
                               errors=errors, form=request.form), 400
    return render_template("mark_sold.html", p=product, inquirers=inquirers, errors={}, form={})


@products_bp.route("/my/listings")
@login_required
def my_listings():
    return render_template("my_listings.html", items=products.list_by_seller(g.user["_id"], AVAILABLE))


@products_bp.route("/my/sold")
@login_required
def my_sold():
    return render_template("my_sold.html", items=transactions.sold_by_seller(g.user["_id"]))
