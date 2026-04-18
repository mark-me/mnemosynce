"""Schedule management routes."""

import json
import logging
import threading

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

from web.auth import login_required
from web.scheduler import (
    _schedule_path,
    get_job_status,
    get_scheduler,
    load_schedule,
    remove_schedule,
    save_schedule,
)

logger = logging.getLogger(__name__)
bp = Blueprint("schedule", __name__, url_prefix="/schedule")
_manual_run_active = False


def _validate_cron(expr: str) -> str | None:
    from apscheduler.triggers.cron import CronTrigger

    parts = expr.strip().split()
    if len(parts) != 5:
        return "Cron expression must have exactly 5 fields: minute hour day month weekday"
    try:
        minute, hour, day, month, day_of_week = parts
        CronTrigger(minute=minute, hour=hour, day=day, month=month, day_of_week=day_of_week)
    except Exception as exc:
        return f"Invalid cron expression: {exc}"
    return None


@bp.route("/")
@login_required
def index():
    app = current_app._get_current_object()
    return render_template("web/schedule.html", cfg=load_schedule(app), status=get_job_status(app))


@bp.route("/save", methods=["POST"])
@login_required
def save():
    app = current_app._get_current_object()
    cron = request.form.get("cron", "").strip()
    enabled = request.form.get("enabled") == "on"
    error = _validate_cron(cron)
    if error:
        flash(error, "danger")
        return redirect(url_for("schedule.index"))
    cfg = {"cron": cron, "enabled": enabled}
    try:
        if enabled:
            save_schedule(app, cfg)
            flash(f"Schedule saved and active: {cron}", "success")
        else:
            _schedule_path(app).write_text(json.dumps(cfg, indent=2), encoding="utf-8")
            sched = get_scheduler()
            if sched.get_job("backup_run"):
                sched.remove_job("backup_run")
            flash("Schedule saved but disabled.", "info")
    except Exception as exc:
        flash(f"Could not save schedule: {exc}", "danger")
    return redirect(url_for("schedule.index"))


@bp.route("/remove", methods=["POST"])
@login_required
def remove():
    remove_schedule(current_app._get_current_object())
    flash("Schedule removed.", "info")
    return redirect(url_for("schedule.index"))


@bp.route("/run-now", methods=["POST"])
@login_required
def run_now():
    global _manual_run_active
    if _manual_run_active:
        flash("A backup run is already in progress.", "warning")
        return redirect(url_for("progress.index"))
    app = current_app._get_current_object()

    def _do_run():
        global _manual_run_active
        _manual_run_active = True
        try:
            from web.scheduler import _run_backup

            _run_backup(app)
        finally:
            _manual_run_active = False

    threading.Thread(target=_do_run, daemon=True, name="manual-backup").start()
    # Redirect to progress page so the user can watch it live
    return redirect(url_for("progress.index"))


@bp.route("/status")
@login_required
def status():
    data = get_job_status(current_app._get_current_object())
    data["manual_running"] = _manual_run_active
    return jsonify(data)
