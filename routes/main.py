import math

from flask import Blueprint, current_app, jsonify, render_template, request

from constants import CATEGORIES, CONDITIONS, SORT_OPTIONS
from db import get_db
from models import products
from services.validators import parse_filters

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    filters = parse_filters(request.args)
    per_page = current_app.config["PER_PAGE"]
    page = filters["page"]
    items, total = products.search(filters, page, per_page)
    pages = max(1, math.ceil(total / per_page))
    if page > pages:  # asked for a page past the end: show the last one
        page = pages
        items, total = products.search(filters, page, per_page)
    # query args to keep in pagination links
    qargs = {k: v for k, v in filters.items()
             if k != "page" and v not in (None, "") and not (k == "sort" and v == "newest")}
    return render_template("index.html", products=items, total=total, page=page, pages=pages,
                           filters=filters, qargs=qargs, categories=CATEGORIES,
                           conditions=CONDITIONS, sort_options=SORT_OPTIONS)


@main_bp.route("/health")
def health():
    try:
        get_db().command("ping")
        return jsonify(status="ok")
    except Exception:
        return jsonify(status="error"), 503
