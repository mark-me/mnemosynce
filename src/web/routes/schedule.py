"""Schedule management routes."""

import json
import logging
import smtplib
import socket
import ssl
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
from web.setup_guard import setup_complete_required
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
@setup_complete_required
def index():
    """Render the standalone schedule management page in operations mode.

    This view is only reachable after setup is complete.  During the wizard,
    schedule configuration is handled by ``/setup/schedule`` instead.

    Requires completed setup; redirects to the wizard otherwise.

    Returns:
        Rendered ``web/schedule.html`` template.
    """
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
    next_url = request.args.get("next") or url_for("schedule.index")
    return redirect(next_url)


@bp.route("/remove", methods=["POST"])
@login_required
def remove():
    remove_schedule(current_app._get_current_object())
    flash("Schedule removed.", "info")
    next_url = request.args.get("next") or url_for("schedule.index")
    return redirect(next_url)


def _check_gmail(app) -> str | None:
    """Test Gmail SMTP reachability and authentication before a backup run.

    Performs a quick SMTP SSL handshake and login attempt using the credentials
    configured in the Flask app.  Returns an error message string when the
    check fails, or ``None`` when credentials are valid.

    Args:
        app: The Flask application instance.

    Returns:
        str | None: A human-readable error message, or ``None`` on success.
    """
    sender = app.config.get("GMAIL_ADDRESS", "")
    password = app.config.get("GMAIL_PASSWORD", "")
    if not sender or not password:
        return "GMAIL_ADDRESS and GMAIL_PASSWORD are not set in the environment."
    try:
        socket.setdefaulttimeout(5)
        socket.getaddrinfo("smtp.gmail.com", 465)
    except OSError:
        return "Cannot reach smtp.gmail.com:465 — check network connectivity."
    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as smtp:
            smtp.login(sender, password)
    except smtplib.SMTPAuthenticationError:
        return (
            "Gmail authentication failed — the app password in your environment "
            "is incorrect or has been revoked."
        )
    except Exception as exc:
        return f"Gmail SMTP error: {exc}"
    return None


@bp.route("/run-now", methods=["POST"])
@login_required
@setup_complete_required
def run_now():
    """Trigger a manual backup run in a background thread.

    Requires completed setup so a backup cannot be triggered before the
    configuration and (if needed) SSH keys are in place.

    Redirects to the progress page so the user can watch the run live.
    """
    """Trigger a manual backup run after pre-flight checks.

    Verifies that Gmail credentials are valid before starting.  If the
    credential check fails the user is redirected back with an actionable
    error message rather than letting the run fail silently at the
    email-report step.

    Returns:
        A redirect to the progress page on success, or back to the referring
        page with a flash message on pre-flight failure.
    """
    global _manual_run_active
    if _manual_run_active:
        flash("A backup run is already in progress.", "warning")
        return redirect(url_for("progress.index"))
    app = current_app._get_current_object()
    gmail_error = _check_gmail(app)
    if gmail_error:
        flash(gmail_error, "danger")
        flash(
            "Fix your Gmail credentials in "
            '<a href="/connections/" class="alert-link">Settings → Connections</a> '
            "before running a backup.",
            "warning",
        )
        return redirect(request.referrer or url_for("schedule.index"))

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
@setup_complete_required
def status():
    """Return a JSON snapshot of the current scheduler and manual-run state.

    Polled by the schedule page to update the "next run" display and the
    running indicator without a full page reload.

    Requires completed setup; redirects to the wizard otherwise.

    Returns:
        JSON object with scheduler status and ``manual_running`` flag.
    """
    data = get_job_status(current_app._get_current_object())
    data["manual_running"] = _manual_run_active
    return jsonify(data)
