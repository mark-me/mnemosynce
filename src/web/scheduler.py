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
    """Initialize per-task scheduled jobs from backup_config.yml.

    Reads the config, computes each task's effective schedule (task-level
    overrides the global default), and registers one APScheduler job per
    task that has an enabled schedule.

    Args:
        app: The Flask application used to load configuration and persist schedule state.
    """
    sched = get_scheduler()
    task_schedules = _load_task_schedules(app)
    for task_name, cron in task_schedules.items():
        _register_task_job(app, sched, task_name, cron)
        logger.info("Restored scheduled job for task '%s': %s", task_name, cron)


def _config_path(app) -> Path:
    """Return the path to backup_config.yml."""
    return Path(app.config["CONFIG_PATH"])


def _load_task_schedules(app) -> dict[str, str]:
    """Read backup_config.yml and return {task_name: cron} for enabled tasks.

    Each task's effective schedule is its own ``schedule.cron`` if present and
    enabled, otherwise the top-level ``schedule.cron`` if present and enabled.
    Tasks with no enabled schedule are omitted.

    Args:
        app: The Flask application instance.

    Returns:
        Ordered dict of task_name → cron expression for all scheduled tasks.
    """
    import yaml as _yaml

    config = _config_path(app)
    if not config.exists():
        return {}
    try:
        raw = _yaml.safe_load(config.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        logger.warning("Could not read config for schedules: %s", exc)
        return {}

    global_sched = raw.get("schedule") or {}
    global_cron = global_sched.get("cron", "") if global_sched.get("enabled") else ""

    result = {}
    for task in raw.get("tasks", []):
        name = task.get("name")
        if not name:
            continue
        task_sched = task.get("schedule") or {}
        if task_sched.get("enabled") and task_sched.get("cron"):
            result[name] = task_sched["cron"]
        elif not task_sched and global_cron:
            result[name] = global_cron
    return result


def load_schedule(app) -> dict | None:
    """Load the global schedule section from backup_config.yml.

    Returns a dict with ``cron`` and ``enabled`` keys, or None when absent.

    Args:
        app: The Flask application instance.
    """
    import yaml as _yaml

    config = _config_path(app)
    if not config.exists():
        return None
    try:
        raw = _yaml.safe_load(config.read_text(encoding="utf-8")) or {}
        sched = raw.get("schedule")
        if isinstance(sched, dict) and sched.get("cron"):
            sched.setdefault("enabled", False)
            return sched
        return None
    except Exception as exc:
        logger.warning("Could not read schedule from config: %s", exc)
        return None


def load_task_schedule(app, task_name: str) -> dict | None:
    """Return the schedule dict for a specific task, or None if not set.

    Args:
        app: The Flask application instance.
        task_name: The task name to look up.
    """
    import yaml as _yaml

    config = _config_path(app)
    if not config.exists():
        return None
    try:
        raw = _yaml.safe_load(config.read_text(encoding="utf-8")) or {}
        for task in raw.get("tasks", []):
            if task.get("name") == task_name:
                return task.get("schedule")
        return None
    except Exception:
        return None


def save_schedule(app, cfg: dict, task_name: str | None = None) -> None:
    """Write a schedule into backup_config.yml and re-register jobs.

    When *task_name* is given the schedule is written under that task.
    Otherwise it updates the top-level global schedule.

    Args:
        app: The Flask application instance.
        cfg: Dict with ``cron`` (str) and ``enabled`` (bool) keys.
        task_name: If set, save as a per-task schedule override.
    """
    import yaml as _yaml

    config = _config_path(app)
    try:
        raw = _yaml.safe_load(config.read_text(encoding="utf-8")) or {}
    except Exception:
        raw = {}

    entry = {"cron": cfg["cron"], "enabled": bool(cfg.get("enabled", False))}

    if task_name:
        for task in raw.get("tasks", []):
            if task.get("name") == task_name:
                task["schedule"] = entry
                break
    else:
        raw["schedule"] = entry

    config.write_text(
        _yaml.dump(raw, default_flow_style=False, allow_unicode=True), encoding="utf-8"
    )
    # Re-register all task jobs to pick up the change
    sched = get_scheduler()
    task_schedules = _load_task_schedules(app)
    # Remove all existing task jobs
    for job in sched.get_jobs():
        if job.id.startswith("backup_task_"):
            sched.remove_job(job.id)
    for tname, cron in task_schedules.items():
        _register_task_job(app, sched, tname, cron)


def remove_schedule(app, task_name: str | None = None) -> None:
    """Remove the schedule from backup_config.yml and unregister the job(s).

    When *task_name* is given only that task's schedule override is removed.
    Otherwise the global schedule is cleared and all task jobs are removed.

    Args:
        app: The Flask application instance.
        task_name: If set, remove only this task's schedule override.
    """
    import yaml as _yaml

    config = _config_path(app)
    if config.exists():
        try:
            raw = _yaml.safe_load(config.read_text(encoding="utf-8")) or {}
            if task_name:
                for task in raw.get("tasks", []):
                    if task.get("name") == task_name:
                        task.pop("schedule", None)
                        break
            else:
                raw.pop("schedule", None)
            config.write_text(
                _yaml.dump(raw, default_flow_style=False, allow_unicode=True), encoding="utf-8"
            )
        except Exception as exc:
            logger.warning("Could not update config when removing schedule: %s", exc)

    sched = get_scheduler()
    if task_name:
        job_id = f"backup_task_{task_name}"
        if sched.get_job(job_id):
            sched.remove_job(job_id)
    else:
        for job in sched.get_jobs():
            if job.id.startswith("backup_task_"):
                sched.remove_job(job.id)


def _register_task_job(app, sched: BackgroundScheduler, task_name: str, cron: str) -> None:
    """Register or replace a per-task scheduled backup job.

    Args:
        app: The Flask application instance.
        sched: The BackgroundScheduler instance.
        task_name: The name of the task to schedule.
        cron: A five-field cron expression string in UTC.

    Raises:
        ValueError: If the cron expression does not contain exactly five fields.
    """
    job_id = f"backup_task_{task_name}"
    if sched.get_job(job_id):
        sched.remove_job(job_id)
    parts = cron.strip().split()
    if len(parts) != 5:
        raise ValueError(f"Cron must have 5 fields, got: {cron!r}")
    minute, hour, day, month, day_of_week = parts
    sched.add_job(
        _run_backup,
        trigger=CronTrigger(
            minute=minute, hour=hour, day=day, month=month, day_of_week=day_of_week, timezone="UTC"
        ),
        id=job_id,
        args=[app, task_name],
        replace_existing=True,
        misfire_grace_time=300,
    )


def _run_backup(app, task_name: str | None = None) -> None:
    """Execute a scheduled backup run for one task within the Flask application context.

    Args:
        app: The Flask application whose configuration and context are used for the backup.
        task_name: The specific task to run, or None to run all tasks.
    """
    with app.app_context():
        config_path = app.config["CONFIG_PATH"]
        gmail_password = app.config.get("GMAIL_PASSWORD", "")

        label = f"task '{task_name}'" if task_name else "all tasks"
        logger.info("Scheduled backup starting — %s", label)

        # Read task names for the progress view
        try:
            import yaml as _yaml
            raw = _yaml.safe_load(Path(config_path).read_text(encoding="utf-8")) or {}
            if task_name:
                task_names = [task_name]
            else:
                task_names = [t["name"] for t in raw.get("tasks", []) if "name" in t]
        except Exception:
            task_names = [task_name] if task_name else []

        state.start(task_names=task_names)

        try:
            _run_with_live_output(app, config_path, gmail_password, task_name=task_name)
            state.finish(success=True)
            logger.info("Scheduled backup completed successfully — %s", label)
        except Exception as exc:
            state.add_line(f"[ERROR] {exc}")
            state.finish(success=False)
            logger.error("Scheduled backup failed: %s", exc, exc_info=True)


def _run_with_live_output(app, config_path, gmail_password, task_name: str | None = None) -> None:
    """Run the backup and mirror log lines into run_state in real time.

    Args:
        app: The Flask application used to provide configuration and context.
        config_path: The path to the backup configuration file.
        gmail_password: The Gmail or app-specific password used for backup email operations.
        task_name: If set, only this task is executed.
    """
    handler = _create_state_handler()
    pkg_logger = _configure_backup_logger(handler)

    try:
        from backup_server.main import main as run_backup

        run_backup(
            file_config=str(config_path),
            password_reader=lambda _: gmail_password,
            task_name=task_name,
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
    """Retrieve scheduled job status for all tasks.

    Returns the global schedule config plus a per-task list with each task's
    effective cron and next run time.

    Args:
        app: The Flask application providing configuration and scheduler context.

    Returns:
        A dict with ``global_schedule``, ``tasks`` (list of per-task status
        dicts), and ``any_scheduled`` (bool).
    """
    sched = get_scheduler()
    global_cfg = load_schedule(app)
    task_schedules = _load_task_schedules(app)

    tasks = []
    for task_name, cron in task_schedules.items():
        job_id = f"backup_task_{task_name}"
        job = sched.get_job(job_id)
        next_run = job.next_run_time if job else None
        task_override = load_task_schedule(app, task_name)
        tasks.append({
            "name": task_name,
            "cron": cron,
            "has_override": bool(task_override),
            "override": task_override,
            "scheduled": job is not None,
            "next_run_utc": next_run.astimezone(UTC).isoformat() if next_run else None,
            "next_run_display": (
                next_run.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC") if next_run else "—"
            ),
        })

    return {
        "global_schedule": global_cfg,
        "tasks": tasks,
        "any_scheduled": bool(tasks),
    }
