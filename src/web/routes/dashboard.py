"""Dashboard routes.

All views require both authentication (``login_required``) and completed
setup (``setup_complete_required``).  Unauthenticated users are redirected
to the login page; users who have not finished the wizard are redirected
to ``/setup/``.

GET /dashboard/              — summary cards + per-task stats table
GET /dashboard/history       — paginated run history (all tasks or one task)
GET /dashboard/history/<task> — history filtered to one task
"""

import logging

from flask import Blueprint, current_app, render_template, request

from web.auth import login_required
from web.setup_guard import setup_complete_required
from web.dashboard_data import get_summary, get_task_history, get_task_stats

logger = logging.getLogger(__name__)
bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")

_PAGE_SIZE = 25


def _db_path():
    return current_app.config["DB_PATH"]


@bp.route("/")
@login_required
@setup_complete_required
def index():
    """Render the main dashboard with summary cards, per-task stats, and recent runs.

    Requires completed setup; redirects to the wizard otherwise.

    Returns:
        Rendered ``web/dashboard.html`` template.
    """
    db = _db_path()
    summary = get_summary(db)
    task_stats = get_task_stats(db)
    # Show the 5 most recent runs inline on the dashboard
    recent = get_task_history(db, limit=5)
    return render_template(
        "web/dashboard.html", summary=summary, task_stats=task_stats, recent=recent
    )


@bp.route("/history")
@bp.route("/history/<task_name>")
@login_required
@setup_complete_required
def history(task_name: str = None):
    """Render a paginated run history, optionally filtered to one task.

    Requires completed setup; redirects to the wizard otherwise.

    Args:
        task_name (str | None): When provided, limits results to this task.

    Returns:
        Rendered ``web/history.html`` template.
    """
    db = _db_path()
    summary = get_summary(db)
    page = max(1, request.args.get("page", 1, type=int))
    runs = get_task_history(db, task_name=task_name, limit=_PAGE_SIZE * page)
    # Simple pagination: re-slice — good enough for a personal tool
    page_runs = runs[_PAGE_SIZE * (page - 1) : _PAGE_SIZE * page]
    has_more = len(runs) == _PAGE_SIZE * page
    return render_template(
        "web/history.html",
        task_name=task_name,
        runs=page_runs,
        tasks=summary["tasks"],
        page=page,
        has_more=has_more,
    )
