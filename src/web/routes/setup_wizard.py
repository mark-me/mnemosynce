"""Setup wizard routes.

Provides a four-step guided setup flow for first-time users:

    Step 1 — Configuration  (/setup/config)
    Step 2 — SSH Keys       (/setup/ssh-keys)   skipped when no remote sources
    Step 3 — Connections    (/setup/connections) skipped when no remote sources
    Step 4 — Schedule       (/setup/schedule)

The wizard is entered automatically when
:func:`web.setup_state.is_setup_complete` returns ``False``.  Setup finishes
via **either** path:

- All four automatic checks pass simultaneously (detected on the next request
  via :func:`web.setup_state.get_setup_status`), or
- The user clicks "Finish setup" on the final step, which calls
  :func:`web.setup_state.mark_setup_complete` to set a session flag.

Each wizard step reuses the underlying route logic (config editor, SSH keys,
connections, schedule) but renders inside ``wizard_base.html`` which provides
the stepper header and suppresses the standard operations navbar.
"""

from __future__ import annotations

import logging

from flask import Blueprint, current_app, redirect, render_template, url_for

from web.auth import login_required
from web.routes.config_editor import _config_path, _read_raw
from web.routes.ssh_keys import _list_keys
from web.scheduler import get_job_status, load_schedule
from web.setup_state import get_setup_status, is_setup_complete, mark_setup_complete

logger = logging.getLogger(__name__)

bp = Blueprint("setup", __name__, url_prefix="/setup")

# Ordered wizard step definitions.  ``id`` must match a key in the
# setup_status dict returned by :func:`web.setup_state.get_setup_status`.
WIZARD_STEPS: list[dict] = [
    {
        "id": "config",
        "label": "Configuration",
        "icon": "bi-file-earmark-code",
        "route": "setup.step_config",
    },
    {
        "id": "ssh_key",
        "label": "SSH Keys",
        "icon": "bi-key",
        "route": "setup.step_ssh_keys",
    },
    {
        "id": "connection",
        "label": "Connections",
        "icon": "bi-wifi",
        "route": "setup.step_connections",
    },
    {
        "id": "schedule",
        "label": "Schedule",
        "icon": "bi-clock-history",
        "route": "setup.step_schedule",
    },
]


def _visible_steps(has_remote: bool) -> list[dict]:
    """Return the wizard steps that apply given the current config.

    SSH Keys and Connections are omitted when the backup configuration
    contains only local source paths — there is no remote host to key into.

    Args:
        has_remote (bool): Whether the current config has any remote sources.

    Returns:
        list[dict]: Ordered list of step descriptors that should be shown.
    """
    if has_remote:
        return WIZARD_STEPS
    return [s for s in WIZARD_STEPS if s["id"] not in ("ssh_key", "connection")]


def _current_step_index(status: dict, steps: list[dict]) -> int:
    """Return the index of the first incomplete step in the visible list.

    If all steps are satisfied the index of the last step is returned so the
    user sees the final page with the "Finish setup" button.

    Args:
        status (dict): Output of :func:`web.setup_state.get_setup_status`.
        steps (list[dict]): The ordered visible steps for this session.

    Returns:
        int: Zero-based index of the first incomplete step, or the last step
        index when all steps are done.
    """
    for i, step in enumerate(steps):
        if not status.get(step["id"], False):
            return i
    return len(steps) - 1


def _step_context(status: dict) -> dict:
    """Build the template context shared by all wizard step pages.

    Args:
        status (dict): Output of :func:`web.setup_state.get_setup_status`.

    Returns:
        dict: Template variables for the stepper header and step navigation.
    """
    steps = _visible_steps(status["has_remote_sources"])
    current_idx = _current_step_index(status, steps)
    return {
        "wizard_steps": steps,
        "wizard_current": current_idx,
        "setup_status": status,
    }


def _next_url(status: dict, current_step_id: str) -> str | None:
    """Return the URL for the next wizard step after ``current_step_id``.

    Args:
        status (dict): Output of :func:`web.setup_state.get_setup_status`.
        current_step_id (str): The ``id`` of the step currently being rendered.

    Returns:
        str | None: URL of the next step, or ``None`` when this is the last
        step and setup is not yet complete.
    """
    steps = _visible_steps(status["has_remote_sources"])
    ids = [s["id"] for s in steps]
    try:
        idx = ids.index(current_step_id)
    except ValueError:
        return None
    if idx + 1 < len(steps):
        return url_for(steps[idx + 1]["route"])
    return None


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


@bp.route("/")
@login_required
def index():
    """Redirect to the first incomplete wizard step, or the dashboard.

    This is the canonical wizard entry point used by the ``setup_complete_required``
    decorator.  It reads the current setup status and forwards to either the
    first incomplete step or the dashboard when setup is already complete.

    Returns:
        A redirect response to the appropriate destination.
    """
    app = current_app._get_current_object()
    if is_setup_complete(app):
        return redirect(url_for("dashboard.index"))

    status = get_setup_status(app)
    steps = _visible_steps(status["has_remote_sources"])
    first_incomplete = next(
        (s for s in steps if not status.get(s["id"], False)),
        steps[0],
    )
    return redirect(url_for(first_incomplete["route"]))


# ---------------------------------------------------------------------------
# Explicit finish endpoint
# ---------------------------------------------------------------------------


@bp.route("/complete", methods=["POST"])
@login_required
def complete():
    """Mark setup as explicitly complete and redirect to the dashboard.

    This endpoint is called when the user clicks "Finish setup" on the final
    wizard step.  It sets the ``setup_explicitly_complete`` session flag via
    :func:`web.setup_state.mark_setup_complete` so that
    :func:`web.setup_state.is_setup_complete` returns ``True`` on all
    subsequent requests, regardless of whether the automatic checks are all
    satisfied yet.

    Returns:
        A redirect response to the dashboard.
    """
    mark_setup_complete()
    return redirect(url_for("dashboard.index"))


# ---------------------------------------------------------------------------
# Step 1 — Configuration
# ---------------------------------------------------------------------------


@bp.route("/config")
@login_required
def step_config():
    """Render the configuration editor inside the wizard shell.

    The YAML editor is pre-populated with the saved config or the default
    template.  Saving is handled by the existing ``POST /config/`` route,
    which writes to disk and redirects back to this page via the
    ``next`` query parameter set in the form action.

    Returns:
        Rendered ``web/wizard_config.html`` template.
    """
    app = current_app._get_current_object()
    status = get_setup_status(app)
    ctx = _step_context(status)
    ctx["raw_yaml"] = _read_raw()
    ctx["file_exists"] = _config_path().exists()
    ctx["errors"] = []
    ctx["next_url"] = _next_url(status, "config")
    return render_template("web/wizard_config.html", **ctx)


# ---------------------------------------------------------------------------
# Step 2 — SSH Keys
# ---------------------------------------------------------------------------


@bp.route("/ssh-keys")
@login_required
def step_ssh_keys():
    """Render the SSH key manager inside the wizard shell.

    Generating and deleting keys is handled by the existing SSH key routes,
    which redirect back here after each action so the stepper stays visible.
    If the config has no remote sources this step is skipped automatically.

    Returns:
        Rendered ``web/wizard_ssh_keys.html`` template, or a redirect to the
        connections step if no remote sources are configured.
    """
    app = current_app._get_current_object()
    status = get_setup_status(app)

    if not status["has_remote_sources"]:
        return redirect(url_for("setup.step_schedule"))

    ctx = _step_context(status)
    ctx["keys"] = _list_keys()
    ctx["next_url"] = _next_url(status, "ssh_key")
    return render_template("web/wizard_ssh_keys.html", **ctx)


# ---------------------------------------------------------------------------
# Step 3 — Connections
# ---------------------------------------------------------------------------


@bp.route("/connections")
@login_required
def step_connections():
    """Render the connection tester inside the wizard shell.

    SSH and email tests call the same JSON endpoints as the standalone
    connections page.  A successful test records the result via
    :func:`web.setup_state.mark_connection_tested` and the step badge
    updates on the next page load.  If the config has no remote sources
    this step is skipped automatically.

    Returns:
        Rendered ``web/wizard_connections.html`` template, or a redirect to
        the schedule step if no remote sources are configured.
    """
    app = current_app._get_current_object()
    status = get_setup_status(app)

    if not status["has_remote_sources"]:
        return redirect(url_for("setup.step_schedule"))

    ctx = _step_context(status)
    ctx["next_url"] = _next_url(status, "connection")
    return render_template("web/wizard_connections.html", **ctx)


# ---------------------------------------------------------------------------
# Step 4 — Schedule
# ---------------------------------------------------------------------------


@bp.route("/schedule")
@login_required
def step_schedule():
    """Render the schedule configuration page inside the wizard shell.

    Schedule save and remove actions are handled by the existing schedule
    routes, which redirect back here.  When all checks pass automatically
    the "Finish setup" button is shown as a primary CTA alongside the
    manual finish form.

    Returns:
        Rendered ``web/wizard_schedule.html`` template.
    """
    app = current_app._get_current_object()
    status = get_setup_status(app)
    ctx = _step_context(status)
    ctx["cfg"] = load_schedule(app)
    ctx["job_status"] = get_job_status(app)
    # all_checks_pass tells the template whether to show the auto-complete
    # banner vs the manual "Finish setup" button.
    all_checks = (
        status["config"]
        and status["ssh_key"]
        and status["connection"]
        and status["schedule"]
    )
    ctx["all_checks_pass"] = all_checks
    return render_template("web/wizard_schedule.html", **ctx)
