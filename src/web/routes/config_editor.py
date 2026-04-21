"""YAML configuration editor routes."""

import logging
import re
from pathlib import Path

import yaml
from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from web.auth import login_required

logger = logging.getLogger(__name__)
bp = Blueprint("config_editor", __name__, url_prefix="/config")
_SESSION_KEY = "config_draft"


def _config_path():
    """Return the filesystem path to the active backup configuration file.

    This reads the CONFIG_PATH setting from the current Flask application
    so helper functions and routes can load or overwrite the YAML config.

    Returns:
        The Path-like object configured as CONFIG_PATH on the Flask app.
    """
    return current_app.config["CONFIG_PATH"]


def _read_raw() -> str:
    """Read the current raw YAML configuration text from disk or a template.

    This returns the saved config file contents when it exists, or a
    starter template string when no configuration has been created yet.

    Returns:
        str: The raw YAML configuration text to display in the editor.
    """
    path = _config_path()
    return path.read_text(encoding="utf-8") if path.exists() else _empty_template()


def _empty_template() -> str:
    """Return the default starter YAML template for a new backup configuration.

    This template provides sensible placeholder values and structure for
    local and remote backup directories, email settings, and an example task.

    Returns:
        str: A multi-line YAML string used to seed a new configuration file.
    """
    return """\
# Mnemosynce configuration
dir_backup_local: /mnt/backup/local
dir_backup_remote: user@backup-host:/mnt/backup/remote
email_sender: your.account@gmail.com
email_report: you@example.com
# email_admin: admin@example.com
tasks:
  - name: MyBackup
    dir_source: /data
    excludes:
      - tmp
      - .cache
"""


_REMOTE_RE = re.compile(r"^[^@]+@[^:]+:.+$")


def _check_local_paths(parsed: dict) -> list[str]:
    """Return non-blocking warnings for local paths that do not exist on disk.

    Only local (non-SSH) paths are checked — remote ``user@host:/path``
    sources cannot be tested from this process.  The warnings are advisory:
    the config is still saved so the user does not lose their work.

    Args:
        parsed (dict): The already-validated YAML config as a Python dict.

    Returns:
        list[str]: Warning strings for each missing local path, possibly empty.
    """
    warnings: list[str] = []
    for field in ("dir_backup_local", "dir_backup_remote"):
        value = parsed.get(field, "")
        if value and not _REMOTE_RE.match(str(value)):
            if not Path(str(value)).is_dir():
                warnings.append(
                    f"Path not found: \"{value}\" ({field}) — "
                    "make sure the volume is mounted."
                )
    for task in parsed.get("tasks") or []:
        if not isinstance(task, dict):
            continue
        source = str(task.get("dir_source", ""))
        if source and not _REMOTE_RE.match(source):
            if not Path(source).is_dir():
                warnings.append(
                    f"Path not found: \"{source}\" "
                    f"(task \"{task.get('name', '?')}\") — "
                    "make sure the volume is mounted."
                )
    return warnings


def _validate(raw_yaml: str) -> list:
    """Validate raw YAML configuration text and return any human-readable errors.

    This checks that the YAML parses, has the expected top-level structure
    and required keys, and that each task entry is shaped correctly.

    Args:
        raw_yaml (str): The raw YAML configuration text submitted by the user.

    Returns:
        list: A list of error message strings; empty when the configuration is valid.
    """
    parsed, parse_error = _parse_yaml(raw_yaml)
    if parse_error:
        return [parse_error]

    if not isinstance(parsed, dict):
        return ["Config must be a YAML mapping."]

    errors: list[str] = []
    _validate_required_keys(parsed, errors)
    _validate_tasks_section(parsed, errors)
    return errors


def _parse_yaml(raw_yaml: str) -> tuple[object, str | None]:
    """Parse YAML and return (parsed_obj, error_message_or_None)."""
    try:
        return yaml.safe_load(raw_yaml), None
    except yaml.YAMLError as exc:
        return None, f"YAML syntax error: {exc}"


def _validate_required_keys(parsed: dict, errors: list[str]) -> None:
    """Validate presence of required top-level keys."""
    required = ["dir_backup_local", "dir_backup_remote", "email_sender", "email_report", "tasks"]
    if missing := [k for k in required if k not in parsed]:
        errors.append(f"Missing required keys: {', '.join(missing)}")


def _validate_tasks_section(parsed: dict, errors: list[str]) -> None:
    """Validate the structure of the 'tasks' section."""
    tasks = parsed.get("tasks")
    if isinstance(tasks, list):
        _validate_each_task(tasks, errors)
    elif tasks is not None:
        errors.append("'tasks' must be a list.")


def _validate_each_task(tasks: list, errors: list[str]) -> None:
    """Validate individual task entries."""
    for i, task in enumerate(tasks):
        if not isinstance(task, dict):
            errors.append(f"Task {i + 1} must be a mapping.")
            continue
        for key in ("name", "dir_source"):
            if key not in task:
                name = task.get("name", f"#{i + 1}")
                errors.append(f"Task '{name}' is missing required key '{key}'.")


@bp.route("/", methods=["GET"])
@login_required
def editor():
    """Render the YAML configuration editor with the current or template config.

    This clears any in-progress draft from the session and displays the
    saved configuration file if it exists, or a starter template otherwise.
    """
    session.pop(_SESSION_KEY, None)
    return render_template(
        "web/config_editor.html",
        raw_yaml=_read_raw(),
        file_exists=_config_path().exists(),
        errors=[],
    )


@bp.route("/", methods=["POST"])
@login_required
def save():
    """Validate and persist posted YAML configuration from the editor form.

    This runs structural checks on the submitted YAML, redisplaying the
    editor with error messages when validation fails, or writes the new
    configuration to disk and redirects back to the editor on success.

    Returns:
        A rendered editor template with validation errors and 422 status
        for invalid input, or a redirect response after a successful save.
    """
    raw = request.form.get("raw_yaml", "")
    if errors := _validate(raw):
        return _render_validation_errors(raw, errors)

    return _persist_and_redirect(raw)


def _render_validation_errors(raw: str, errors: list[str]):
    """Render the editor template with validation errors for an invalid config."""
    session[_SESSION_KEY] = raw
    for error in errors:
        flash(error, "danger")
    return (
        render_template(
            "web/config_editor.html",
            raw_yaml=raw,
            file_exists=_config_path().exists(),
            errors=errors,
        ),
        422,
    )


def _persist_and_redirect(raw: str):
    """Write a valid configuration to disk, emit warnings, and redirect."""
    _config_path().write_text(raw, encoding="utf-8")
    session.pop(_SESSION_KEY, None)
    parsed = yaml.safe_load(raw)
    path_warnings = _check_local_paths(parsed) if isinstance(parsed, dict) else []
    if path_warnings:
        for w in path_warnings:
            flash(w, "warning")
        flash("Configuration saved — check the warnings above.", "success")
    else:
        flash("Configuration saved successfully.", "success")
    next_url = request.args.get("next") or url_for("config_editor.editor")
    return redirect(next_url)


@bp.route("/reset", methods=["POST"])
@login_required
def reset():
    """Discard any unsaved configuration draft and reload the saved config.

    This clears the draft YAML from the session, shows an informational
    flash message, and redirects back to the editor view.
    """
    session.pop(_SESSION_KEY, None)
    flash("Edits discarded — reverted to saved version.", "info")
    return redirect(url_for("config_editor.editor"))
