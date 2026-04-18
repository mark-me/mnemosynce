"""Main routes — home page and any top-level views."""

from flask import Blueprint, render_template

from web.auth import login_required

bp = Blueprint("main", __name__)


@bp.route("/")
@login_required
def index():
    return render_template("web/index.html")
