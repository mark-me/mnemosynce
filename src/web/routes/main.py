"""Main routes — home page entry point."""

from flask import Blueprint, redirect, render_template, url_for, current_app

from web.auth import login_required
from web.setup_state import is_setup_complete

bp = Blueprint("main", __name__)


@bp.route("/")
@login_required
def index():
    """Redirect to the dashboard when setup is complete, or to the wizard.

    This replaces the static home tile grid.  Once a user has finished the
    setup wizard the home route transparently forwards them to the dashboard,
    which is the primary operational view.  New users land in the wizard.

    Returns:
        A redirect response to either the dashboard or the setup wizard.
    """
    app = current_app._get_current_object()
    if is_setup_complete(app):
        return redirect(url_for("dashboard.index"))
    return redirect(url_for("setup.index"))
