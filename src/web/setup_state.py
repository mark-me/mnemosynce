"""Setup state tracking via the Flask session.

Determines whether the four setup prerequisites have been met and stores
transient state — specifically the connection-test result — in the Flask
session.  All other checks are derived live from the filesystem so they
always reflect the true system state without a separate persistence layer.

The four checks are:

1. **config** — ``backup_config.yml`` exists and passes structural validation.
2. **ssh_key** — at least one ed25519 keypair exists in ``SSH_KEY_DIR``.
   Automatically satisfied when the config has no remote sources.
3. **connection** — at least one SSH or email test has passed in this
   browser session, OR the session flag ``setup_explicitly_complete`` is
   set (user clicked "Finish setup").
   Automatically satisfied when the config has no remote sources.
4. **schedule** — a schedule has been saved and enabled in ``schedule.json``.

Setup is considered **complete** when:

- All four checks are satisfied simultaneously, **or**
- The user has clicked "Finish setup" (``setup_explicitly_complete`` is
  set in the session).

Because state is session-scoped, the wizard re-runs after a server restart
if the filesystem checks alone are not all satisfied.  This is intentional:
it gives the user an opportunity to re-verify connections after a restart
without requiring a separate "reset" action.

Example usage::

    from web.setup_state import get_setup_status, mark_connection_tested

    status = get_setup_status(app)
    # {'config': True, 'ssh_key': False, 'connection': False,
    #  'schedule': False, 'complete': False, 'has_remote_sources': True}

    mark_connection_tested()   # call inside a request context
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import yaml
from flask import session

logger = logging.getLogger(__name__)

# Session key used to persist the connection-test flag across requests.
_SESSION_CONN_KEY = "setup_connection_tested"

# Session key set when the user explicitly clicks "Finish setup".
_SESSION_DONE_KEY = "setup_explicitly_complete"


# ---------------------------------------------------------------------------
# Live filesystem checks
# ---------------------------------------------------------------------------


def _check_config(app) -> bool:
    """Return True if the backup configuration file exists and is structurally valid.

    Args:
        app: The Flask application instance.

    Returns:
        bool: ``True`` when the config file exists and contains all required keys.
    """
    config_path = Path(app.config["CONFIG_PATH"])
    if not config_path.exists():
        return False
    try:
        with config_path.open(encoding="utf-8") as fh:
            parsed = yaml.safe_load(fh)
        required = [
            "dir_backup_local",
            "dir_backup_remote",
            "email_sender",
            "email_report",
            "tasks",
        ]
        return isinstance(parsed, dict) and all(k in parsed for k in required)
    except Exception:
        return False


def _check_ssh_key(app) -> bool:
    """Return True if at least one complete SSH keypair exists in SSH_KEY_DIR.

    A complete keypair has both a private key file and a corresponding
    ``.pub`` file.

    Args:
        app: The Flask application instance.

    Returns:
        bool: ``True`` when at least one valid keypair is found.
    """
    ssh_dir = Path(app.config["SSH_KEY_DIR"])
    return any(pub.with_suffix("").exists() for pub in ssh_dir.glob("*.pub"))


def _check_schedule(app) -> bool:
    """Return True if a schedule has been saved and enabled on disk.

    Args:
        app: The Flask application instance.

    Returns:
        bool: ``True`` when ``schedule.json`` exists and its ``enabled`` field
        is truthy.
    """
    schedule_path = Path(app.config["DATA_ROOT"]) / "schedule.json"
    if not schedule_path.exists():
        return False
    try:
        cfg = json.loads(schedule_path.read_text(encoding="utf-8"))
        return bool(cfg.get("enabled"))
    except Exception:
        return False


def _has_remote_sources(app) -> bool:
    """Return True if any backup task source path is a remote SSH address.

    A remote source contains ``@`` (e.g. ``user@host:/path``).  When no
    remote sources are present the SSH key and connection-test steps are not
    required and are skipped automatically in the wizard.

    Args:
        app: The Flask application instance.

    Returns:
        bool: ``True`` when at least one task has a remote ``dir_source``.
    """
    config_path = Path(app.config["CONFIG_PATH"])
    if not config_path.exists():
        return False
    try:
        with config_path.open(encoding="utf-8") as fh:
            parsed = yaml.safe_load(fh)
        tasks = parsed.get("tasks", []) if isinstance(parsed, dict) else []
        return any(
            "@" in str(task.get("dir_source", ""))
            for task in tasks
            if isinstance(task, dict)
        )
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Session-backed checks
# ---------------------------------------------------------------------------


def mark_connection_tested() -> None:
    """Record in the session that a connection test has passed.

    Must be called inside an active Flask request context.  The flag persists
    for the lifetime of the browser session (or until the session is cleared).
    """
    session[_SESSION_CONN_KEY] = True


def mark_setup_complete() -> None:
    """Set the explicit completion flag in the session.

    Called when the user clicks "Finish setup" at the end of the wizard,
    regardless of whether all automatic checks are satisfied.  Must be called
    inside an active Flask request context.
    """
    session[_SESSION_DONE_KEY] = True


def _connection_tested() -> bool:
    """Return True if the connection-test session flag is set.

    Returns:
        bool: The value of the ``setup_connection_tested`` session key.
    """
    return bool(session.get(_SESSION_CONN_KEY))


def _explicitly_complete() -> bool:
    """Return True if the user has explicitly marked setup as finished.

    Returns:
        bool: The value of the ``setup_explicitly_complete`` session key.
    """
    return bool(session.get(_SESSION_DONE_KEY))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_setup_status(app) -> dict:
    """Compute and return the current setup readiness for all four steps.

    Each step is evaluated by inspecting the filesystem and the current
    session.  The ``ssh_key`` and ``connection`` checks are automatically
    satisfied when the config contains no remote sources.

    Setup is **complete** when all four checks pass, or when the user has
    explicitly clicked "Finish setup" (``setup_explicitly_complete`` in
    the session).

    Args:
        app: The Flask application instance.

    Returns:
        dict: A mapping with boolean values for each step key plus two extra
        keys — ``complete`` (bool) and ``has_remote_sources`` (bool).

        Example::

            {
                'config': True,
                'ssh_key': True,
                'connection': False,
                'schedule': False,
                'complete': False,
                'has_remote_sources': True,
            }
    """
    has_remote = _has_remote_sources(app)
    config_ok = _check_config(app)
    ssh_ok = _check_ssh_key(app) if has_remote else True
    schedule_ok = _check_schedule(app)
    connection_ok = _connection_tested() if has_remote else True

    all_checks_pass = config_ok and ssh_ok and connection_ok and schedule_ok
    complete = all_checks_pass or _explicitly_complete()

    return {
        "config": config_ok,
        "ssh_key": ssh_ok,
        "connection": connection_ok,
        "schedule": schedule_ok,
        "complete": complete,
        "has_remote_sources": has_remote,
    }


def is_setup_complete(app) -> bool:
    """Return True when setup is considered finished.

    This is a convenience wrapper around :func:`get_setup_status` for use
    in route decorators and the application factory.

    Args:
        app: The Flask application instance.

    Returns:
        bool: ``True`` if setup is fully complete.
    """
    return get_setup_status(app)["complete"]
