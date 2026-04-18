"""APScheduler singleton for the backup runner.

Free of Flask imports so it can be imported without an application context.
The Flask app factory calls init_scheduler(app) once at startup.
Schedule state is persisted to DATA_ROOT/schedule.json.

This module also drives run_state updates so the progress view has live data.
"""

import json
import logging
import logging as _logging
import threading
from datetime import UTC
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from web.run_state import STEP_NAMES, state

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None
_job_id = "backup_run"
_lock = threading.Lock()
_SCHEDULE_FILE = "schedule.json"


def get_scheduler() -> BackgroundScheduler:
    """Return the shared APScheduler instance used for scheduled backups.

    This lazily creates and starts a singleton BackgroundScheduler configured
    for UTC, so all scheduled jobs in the app share the same scheduler.

    Returns:
        The global BackgroundScheduler instance, creating it if necessary.
    """
    global _scheduler
    if _scheduler is None:
        with _lock:
            if _scheduler is None:
                _scheduler = BackgroundScheduler(timezone="UTC")
                _scheduler.start()
                logger.info("APScheduler started")
    return _scheduler


def init_scheduler(app) -> None:
    """Initialize the global scheduler from persisted schedule configuration.

    This restores any previously saved cron schedule and re-registers the
    scheduled backup job so it will run automatically if it is enabled.

    Args:
        app: The Flask application used to load configuration and persist schedule state.
    """
    sched = get_scheduler()
    cfg = load_schedule(app)
    if cfg and cfg.get("enabled"):
        _register_job(app, sched, cfg["cron"])
        logger.info("Restored scheduled backup job: %s", cfg["cron"])


def _schedule_path(app) -> Path:
    """Build the filesystem path to the persisted schedule configuration file.

    This computes the location of the schedule JSON file inside the application's
    data root so schedule state can be loaded from and saved to a consistent place.

    Args:
        app: The Flask application whose DATA_ROOT configuration determines the schedule path.

    Returns:
        The full Path to the schedule.json file under the app's data directory.
    """
    return Path(app.config["DATA_ROOT"]) / _SCHEDULE_FILE


def load_schedule(app) -> dict | None:
    """Load the persisted schedule configuration from disk if it exists.

    This reads the JSON schedule file from the application's data directory and
    returns its contents as a dictionary, or None when no schedule is stored or it cannot be read.

    Args:
        app: The Flask application whose configuration determines where the schedule file is stored.

    Returns:
        A dictionary representing the saved schedule configuration, or None if no valid
        schedule file is available.
    """
    path = _schedule_path(app)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Could not read schedule file: %s", exc)
        return None


def save_schedule(app, cfg: dict) -> None:
    """Persist the given schedule configuration and update the active job.

    This writes the schedule data to the JSON file on disk and immediately
    re-registers the scheduled backup job using the provided cron expression.

    Args:
        app: The Flask application whose configuration determines where the schedule is stored.
        cfg: A dictionary containing the schedule configuration, including a "cron" field.
    """
    _schedule_path(app).write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    _register_job(app, get_scheduler(), cfg["cron"])


def remove_schedule(app) -> None:
    """Delete any stored schedule configuration and unregister the scheduled job.

    This clears the persisted schedule file from disk and removes the current
    backup job from the scheduler so no further automatic runs will occur.

    Args:
        app: The Flask application whose configuration determines the schedule file location.
    """
    path = _schedule_path(app)
    if path.exists():
        path.unlink()
    sched = get_scheduler()
    if sched.get_job(_job_id):
        sched.remove_job(_job_id)


def _register_job(app, sched: BackgroundScheduler, cron: str) -> None:
    """Register or replace the scheduled backup job with the given cron expression.

    This updates the APScheduler instance so that a single backup job is configured
    to run according to the provided five-field cron schedule in UTC.

    Args:
        app: The Flask application that will be passed into the backup job when it runs.
        sched: The BackgroundScheduler instance that manages the scheduled backup job.
        cron: A five-field cron expression string defining when the backup should run.

    Raises:
        ValueError: If the cron expression does not contain exactly five whitespace-separated fields.
    """
    if sched.get_job(_job_id):
        sched.remove_job(_job_id)
    parts = cron.strip().split()
    if len(parts) != 5:
        raise ValueError(f"Cron must have 5 fields, got: {cron!r}")
    minute, hour, day, month, day_of_week = parts
    sched.add_job(
        _run_backup,
        trigger=CronTrigger(
            minute=minute, hour=hour, day=day, month=month, day_of_week=day_of_week, timezone="UTC"
        ),
        id=_job_id,
        args=[app],
        replace_existing=True,
        misfire_grace_time=300,
    )


def _run_backup(app) -> None:
    """Execute a scheduled backup run within the Flask application context.

    This coordinates calling the backup runner, streams progress into run_state,
    and records whether the scheduled backup completed successfully or failed.

    Args:
        app: The Flask application whose configuration and context are used for the backup.
    """
    with app.app_context():
        config_path = app.config["CONFIG_PATH"]
        gmail_password = app.config.get("GMAIL_PASSWORD", "")
        task_label = config_path.stem  # e.g. "backup_config"

        logger.info("Scheduled backup starting — config: %s", config_path)
        state.start(task_name=str(config_path.name))

        try:
            # Monkey-patch the backup runner to intercept log output into run_state
            _run_with_live_output(app, config_path, gmail_password)
            state.finish(success=True)
            logger.info("Scheduled backup completed successfully")
        except Exception as exc:
            state.add_line(f"[ERROR] {exc}")
            state.finish(success=False)
            logger.error("Scheduled backup failed: %s", exc, exc_info=True)


def _run_with_live_output(app, config_path, gmail_password) -> None:
    """Run the backup and mirror log lines into run_state in real time.

    Args:
        app: The Flask application used to provide configuration and context.
        config_path: The path to the backup configuration file.
        gmail_password: The Gmail or app-specific password used for backup email operations.

    We add a logging handler that captures every log record emitted by the
    backup_server package and pushes it to run_state.  This means the
    progress view shows the same information that goes into log.json,
    without any extra instrumentation of the backup code itself.
    """
    handler = _create_state_handler()
    pkg_logger = _configure_backup_logger(handler)

    try:
        from backup_server.main import main as run_backup

        run_backup(
            file_config=str(config_path),
            password_reader=lambda _: gmail_password,
        )
    finally:
        pkg_logger.removeHandler(handler)


def _create_state_handler() -> _logging.Handler:
    """Create a logging handler that mirrors backup progress into run_state.

    This handler formats log records, appends them to run_state, and updates
    step status based on recognised phrases in the message.
    """

    class _StateHandler(_logging.Handler):
        """Forwards log records to run_state and updates step status."""

        _STEP_START = {
            "backup": "start backup",
            "retention": "applying retention",
            "sync": "syncing local",
        }
        _STEP_SUCCESS = {
            "backup": "step 'backup' succeeded",
            "retention": "step 'retention' succeeded",
            "sync": "step 'sync' succeeded",
        }
        _STEP_FAIL = {
            "backup": "step 'backup' failed",
            "retention": "step 'retention' failed",
            "sync": "step 'sync' failed",
        }

        def emit(self, record: _logging.LogRecord) -> None:
            """Process a log record and update run_state with progress information.

            This forwards the formatted log message to run_state and infers step
            start, success, or failure by matching known phrases in the message.

            Args:
                record: The log record emitted by the backup_server logger.
            """
            msg = self.format(record)
            state.add_line(msg)
            low = msg.lower()
            for step in STEP_NAMES:
                if self._STEP_START[step] in low:
                    state.step_running(step)
                elif self._STEP_SUCCESS[step] in low:
                    state.step_done(step, success=True)
                elif self._STEP_FAIL[step] in low:
                    state.step_done(step, success=False)

    handler = _StateHandler()
    handler.setFormatter(_logging.Formatter("%(levelname)s %(name)s — %(message)s"))
    handler.setLevel(_logging.DEBUG)
    return handler


def _configure_backup_logger(handler: _logging.Handler) -> _logging.Logger:
    """Attach the run_state handler to the backup logger and set its log level.

    This configures the ``backup_server`` logger to emit detailed debug output and
    ensures that every log record flows through the provided handler for progress tracking.

    Args:
        handler: The logging handler that will receive backup log records.

    Returns:
        The configured backup logger so callers can later remove the handler.
    """
    pkg_logger = _logging.getLogger("backup_server")
    pkg_logger.addHandler(handler)
    pkg_logger.setLevel(_logging.DEBUG)
    return pkg_logger


def get_job_status(app) -> dict:
    """Retrieve the current scheduled backup job status and next run information.

    This reports whether a backup job is scheduled and enabled, and includes
    the cron expression and the next scheduled run time in UTC and display formats.

    Args:
        app: The Flask application providing configuration and scheduler context.

    Returns:
        A dictionary describing the schedule status with fields such as
        "scheduled", "enabled", "cron", "next_run_utc", and "next_run_display".
    """
    sched = get_scheduler()
    job = sched.get_job(_job_id)
    cfg = load_schedule(app)
    if job is None or cfg is None:
        return {"scheduled": False, "enabled": False}
    next_run = job.next_run_time
    return {
        "scheduled": True,
        "enabled": cfg.get("enabled", False),
        "cron": cfg.get("cron", ""),
        "next_run_utc": next_run.astimezone(UTC).isoformat() if next_run else None,
        "next_run_display": (
            next_run.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC") if next_run else "—"
        ),
    }
