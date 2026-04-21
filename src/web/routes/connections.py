"""Connection testing routes."""

import logging
import smtplib
import socket
import ssl
import subprocess
from email.message import EmailMessage

from flask import Blueprint, current_app, jsonify, render_template, request

from web.auth import login_required
from web.setup_state import mark_connection_tested

logger = logging.getLogger(__name__)
bp = Blueprint("connections", __name__, url_prefix="/connections")


def _test_ssh(user: str, host: str, path: str) -> dict:
    """Test SSH connectivity to a remote host and optionally a directory path.

    This performs a ping check, verifies SSH login for the given user, and,
    when a path is provided, confirms that the directory exists on the host.

    Args:
        user (str): Username to use when connecting via SSH.
        host (str): Hostname or IP address of the remote machine.
        path (str): Optional directory path on the remote host to verify.

    Returns:
        dict: A result dictionary with overall ``success`` and a ``steps`` list
        describing each individual connectivity check.
    """
    steps: list[dict] = []

    ping_ok = _add_ping_step(steps, host)
    if not ping_ok:
        return {"success": False, "steps": steps}

    ssh_ok = _add_ssh_login_step(steps, user, host)
    if not ssh_ok:
        return {"success": False, "steps": steps}

    if path:
        dir_ok = _add_remote_dir_step(steps, user, host, path)
        return {"success": dir_ok, "steps": steps}

    return {"success": True, "steps": steps}


def _add_ping_step(steps: list[dict], host: str) -> bool:
    """Run a ping check to the host and append the result to steps.

    This sends a single ICMP echo request and records whether the host
    responded, adding a human-readable connectivity step entry.
    """
    result = subprocess.run(
        ["ping", "-c", "1", "-W", "3", host],
        capture_output=True,
        text=True,
    )
    ping_ok = result.returncode == 0
    steps.append(
        {
            "label": f"Ping {host}",
            "ok": ping_ok,
            "detail": "" if ping_ok else "Host unreachable",
        }
    )
    return ping_ok


def _add_ssh_login_step(steps: list[dict], user: str, host: str) -> bool:
    """Attempt SSH login to the host and append the result to steps.

    This runs a non-interactive SSH command to verify credentials and
    connectivity, recording a human-readable outcome for the login step.
    """
    result = subprocess.run(
        ["ssh", "-q", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", f"{user}@{host}", "exit"],
        capture_output=True,
        text=True,
    )
    ssh_ok = result.returncode == 0
    steps.append(
        {
            "label": f"SSH login as {user}@{host}",
            "ok": ssh_ok,
            "detail": "" if ssh_ok else result.stderr.strip() or "SSH login failed",
        }
    )
    return ssh_ok


def _add_remote_dir_step(steps: list[dict], user: str, host: str, path: str) -> bool:
    """Check that a directory exists on the remote host and append the result.

    This runs a remote ``test -d`` command over SSH and records whether the
    target directory is present, adding a human-readable step entry.
    """
    result = subprocess.run(
        [
            "ssh",
            "-q",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=5",
            f"{user}@{host}",
            "test",
            "-d",
            path,
        ],
        capture_output=True,
        text=True,
    )
    dir_ok = result.returncode == 0
    steps.append(
        {
            "label": f"Directory {path} exists",
            "ok": dir_ok,
            "detail": "" if dir_ok else f"Not found: {path}",
        }
    )
    return dir_ok


def _test_email(sender: str, password: str, recipient: str) -> dict:
    """Test Gmail SMTP connectivity, authentication, and sending a test message.

    This first checks that the Gmail SMTP endpoint is reachable, then tries
    to log in with the provided credentials and send a short test email to
    the given recipient, recording each step along the way.

    Args:
        sender (str): The Gmail address used as the SMTP username and From address.
        password (str): The app-specific or account password for the sender address.
        recipient (str): The email address that should receive the test message.

    Returns:
        dict: A result dictionary with overall ``success`` and a ``steps`` list
        describing each individual connectivity and send check.
    """
    steps: list[dict] = []

    reachable = _add_smtp_reachability_step(steps)
    if not reachable:
        return {"success": False, "steps": steps}

    success = _add_smtp_login_and_send_steps(steps, sender, password, recipient)
    return {"success": success, "steps": steps}


def _add_smtp_reachability_step(steps: list[dict]) -> bool:
    """Check DNS/port reachability for the Gmail SMTP endpoint and record the step.

    This resolves and connects to ``smtp.gmail.com:465`` with a short timeout
    to ensure network access is available before attempting SMTP login.

    Args:
        steps (list[dict]): The list that will be extended with the reachability result.

    Returns:
        bool: True if the endpoint is reachable, otherwise False.
    """
    try:
        socket.setdefaulttimeout(5)
        socket.getaddrinfo("smtp.gmail.com", 465)
        steps.append({"label": "Reach smtp.gmail.com:465", "ok": True, "detail": ""})
        return True
    except OSError as exc:
        steps.append({"label": "Reach smtp.gmail.com:465", "ok": False, "detail": str(exc)})
        return False


def _add_smtp_login_and_send_steps(
    steps: list[dict],
    sender: str,
    password: str,
    recipient: str,
) -> bool:
    """Attempt SMTP login and send a test email, recording each step outcome.

    This opens an SSL connection to Gmail's SMTP server, tries to authenticate
    with the supplied credentials, and, on success, sends a small test message
    to the recipient while appending detailed step results.
    """
    try:
        with _open_smtp_connection() as smtp:
            if not _smtp_login(smtp, steps, sender, password):
                return False
            if not _smtp_send_test_email(smtp, steps, sender, recipient):
                return False
        return True
    except smtplib.SMTPAuthenticationError:
        _append_auth_error_step(steps, sender)
        return False
    except Exception as exc:
        _append_send_error_step(steps, exc)
        return False


def _open_smtp_connection() -> smtplib.SMTP_SSL:
    """Open an SSL connection to Gmail's SMTP server."""
    context = ssl.create_default_context()
    return smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context)


def _smtp_login(smtp: smtplib.SMTP_SSL, steps: list[dict], sender: str, password: str) -> bool:
    """Log in to SMTP and record the login step."""
    smtp.login(sender, password)
    steps.append({"label": f"SMTP login as {sender}", "ok": True, "detail": ""})
    return True


def _smtp_send_test_email(
    smtp: smtplib.SMTP_SSL,
    steps: list[dict],
    sender: str,
    recipient: str,
) -> bool:
    """Send a test email and record the send step."""
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = "Mnemosynce — connection test"
    msg.set_content("This is a test email from your Mnemosynce web UI.\n")
    smtp.send_message(msg)
    steps.append({"label": f"Send test email to {recipient}", "ok": True, "detail": ""})
    return True


def _append_auth_error_step(steps: list[dict], sender: str) -> None:
    """Append an authentication error step."""
    steps.append(
        {
            "label": f"SMTP login as {sender}",
            "ok": False,
            "detail": "Authentication failed — check Gmail address and app password.",
        }
    )


def _append_send_error_step(steps: list[dict], exc: Exception) -> None:
    """Append a generic send error step."""
    steps.append({"label": "Send test email", "ok": False, "detail": str(exc)})


@bp.route("/")
@login_required
def index():
    """Render the connections test page for SSH and email checks.

    This view serves the HTML UI where users can trigger connection tests
    and see step-by-step results for SSH and SMTP connectivity.
    """
    return render_template("web/connections.html")


@bp.route("/ssh", methods=["POST"])
@login_required
def test_ssh():
    """Handle an AJAX request to run SSH connection tests and return JSON.

    This validates the incoming payload, runs ping/login/path checks against
    the requested host, and responds with a structured success flag and steps.
    """
    data = request.get_json(silent=True) or {}
    user = data.get("user", "").strip()
    host = data.get("host", "").strip()
    path = data.get("path", "").strip()
    if not user or not host:
        return jsonify({"success": False, "steps": [], "error": "user and host are required"}), 400
    result = _test_ssh(user, host, path)
    if result.get("success"):
        mark_connection_tested()
    return jsonify(result)


@bp.route("/email", methods=["POST"])
@login_required
def test_email():
    """Handle an AJAX request to run email connection tests and return JSON.

    This reads Gmail credentials from configuration, validates the request
    payload, runs SMTP reachability/login/send checks, and responds with a
    structured success flag and step-by-step results.
    """
    data = request.get_json(silent=True) or {}
    sender = current_app.config.get("GMAIL_ADDRESS", "")
    password = current_app.config.get("GMAIL_PASSWORD", "")
    recipient = data.get("recipient", "").strip() or sender
    if not sender or not password:
        return jsonify(
            {
                "success": False,
                "steps": [],
                "error": "GMAIL_ADDRESS and GMAIL_PASSWORD must be set in the environment.",
            }
        ), 400
    result = _test_email(sender, password, recipient)
    if result.get("success"):
        mark_connection_tested()
    return jsonify(result)
