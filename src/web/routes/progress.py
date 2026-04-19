"""Progress view routes.

All views require both authentication (``login_required``) and completed
setup (``setup_complete_required``).  Unauthenticated users are redirected
to the login page; users who have not finished the wizard are redirected
to ``/setup/``.

GET  /progress/          — HTML page showing live or last run output
GET  /progress/stream    — SSE stream of log lines and state updates
GET  /progress/state     — JSON snapshot of the current run state
"""

import json
import logging
import time

from flask import Blueprint, Response, render_template, stream_with_context

from web.auth import login_required
from web.setup_guard import setup_complete_required
from web.run_state import state

logger = logging.getLogger(__name__)
bp = Blueprint("progress", __name__, url_prefix="/progress")

# How long the SSE stream stays open when no run is active (seconds)
_IDLE_TIMEOUT = 30
# Interval between keepalive comments when idle (seconds)
_KEEPALIVE_INTERVAL = 5


@bp.route("/")
@login_required
@setup_complete_required
def index():
    """Render the live progress page showing the current or last run.

    Requires completed setup; redirects to the wizard otherwise.

    Returns:
        Rendered ``web/progress.html`` template.
    """
    snap = state.snapshot()
    return render_template("web/progress.html", snap=snap)


@bp.route("/state")
@login_required
@setup_complete_required
def state_json():
    """Return the current run-state snapshot as JSON.

    Requires completed setup; redirects to the wizard otherwise.

    Returns:
        A JSON ``Response`` containing the output of ``state.snapshot()``.
    """
    return Response(
        json.dumps(state.snapshot()),
        mimetype="application/json",
    )


@bp.route("/stream")
@login_required
@setup_complete_required
def stream():
    """Server-Sent Events stream.

    Sends two event types:
        event: line   — a new log line (data: <text>)
        event: state  — a full state snapshot as JSON (data: <json>)

    The client subscribes once and receives updates until the run finishes,
    then gets a final ``state`` event and the stream closes.
    """

    def generate():
        seq = 0
        idle_since = time.monotonic()

        # Send the initial state immediately so the page renders before logs arrive
        yield _sse("state", json.dumps(state.snapshot()))

        while True:
            snap = state.snapshot()
            new_lines, new_seq = state.lines_from(seq)

            if new_lines:
                idle_since = time.monotonic()
                for line in new_lines:
                    yield _sse("line", line)
                seq = new_seq
                # Also push a state update so step badges refresh
                yield _sse("state", json.dumps(snap))

            elif not snap["active"]:
                # Run has finished (or never started) — send final state and close
                yield _sse("state", json.dumps(snap))
                yield _sse("done", "")
                return

            else:
                # Active but no new lines yet — send keepalive
                if time.monotonic() - idle_since > _KEEPALIVE_INTERVAL:
                    yield ": keepalive\n\n"
                    idle_since = time.monotonic()

            time.sleep(0.3)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering
        },
    )


def _sse(event: str, data: str) -> str:
    return f"event: {event}\ndata: {data}\n\n"
