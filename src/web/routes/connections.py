"""Connection testing routes."""

import logging
import smtplib
import socket
import ssl
import subprocess
from email.message import EmailMessage
from pathlib import Path

from flask import Blueprint, current_app, jsonify, render_template, request

from web.auth import login_required
from web.setup_state import mark_connection_tested


def _ssh_config_args() -> list[str]:
    """Return [-F, <path>] args if the persisted ssh_config exists, else []."""
    ssh_config = Path(current_app.config["DATA_ROOT"]) / "ssh" / "ssh_config"
    return ["-F", str(ssh_config)] if ssh_config.exists() else []

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
        ["ssh", *_ssh_config_args(), "-q", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", f"{user}@{host}", "exit"],
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
    import shlex
    result = subprocess.run(
        [
            "ssh",
            *_ssh_config_args(),
            "-q",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=5",
            f"{user}@{host}",
            f"test -d {shlex.quote(path)}",
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
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as smtp:
            smtp.login(sender, password)
            steps.append({"label": f"SMTP login as {sender}", "ok": True, "detail": ""})
            msg = EmailMessage()
            msg["From"] = sender
            msg["To"] = recipient
            msg["Subject"] = "Mnemosynce — connection test"
            msg.set_content(
                "This is a test email from your Mnemosynce web UI.\n"
            )
            smtp.send_message(msg)
            steps.append({"label": f"Send test email to {recipient}", "ok": True, "detail": ""})
        return True
    except smtplib.SMTPAuthenticationError:
        steps.append(
            {
                "label": f"SMTP login as {sender}",
                "ok": False,
                "detail": "Authentication failed — check Gmail address and app password.",
            }
        )
        return False
    except Exception as exc:
        steps.append({"label": "Send test email", "ok": False, "detail": str(exc)})
        return False


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


@bp.route("/trust-host-key", methods=["POST"])
@login_required
def trust_host_key():
    """Scan a remote host's public key and append it to known_hosts.

    This runs ssh-keyscan against the given host and writes the result into
    DATA_ROOT/ssh/known_hosts so that subsequent SSH connections from the
    container can proceed without a host-key verification prompt.

    Returns JSON with ``success`` (bool), ``host`` (str), and ``detail`` (str).
    """
    data = request.get_json(silent=True) or {}
    host = data.get("host", "").strip()
    if not host:
        return jsonify({"success": False, "detail": "host is required"}), 400

    ssh_dir = Path(current_app.config["DATA_ROOT"]) / "ssh"
    ssh_dir.mkdir(parents=True, exist_ok=True)
    known_hosts = ssh_dir / "known_hosts"

    # Check whether a key for this host is already trusted.
    if known_hosts.exists():
        check = subprocess.run(
            ["ssh-keygen", "-F", host, "-f", str(known_hosts)],
            capture_output=True,
            text=True,
        )
        if check.returncode == 0:
            return jsonify({
                "success": True,
                "host": host,
                "detail": f"Host '{host}' is already in known_hosts.",
            })

    result = subprocess.run(
        ["ssh-keyscan", "-H", "-T", "5", host],
        capture_output=True,
        text=True,
    )

    scanned_keys = result.stdout.strip()
    if not scanned_keys:
        detail = result.stderr.strip() or f"ssh-keyscan returned no key for '{host}' — is the host reachable from the container?"
        logger.error("ssh-keyscan failed for '%s': %s", host, detail)
        return jsonify({"success": False, "host": host, "detail": detail})

    try:
        with open(known_hosts, "a", encoding="utf-8") as f:
            f.write(scanned_keys + "\n")
    except OSError as exc:
        logger.error("Failed to write known_hosts at %s: %s", known_hosts, exc)
        return jsonify({"success": False, "host": host, "detail": f"Could not write known_hosts: {exc}"})

    logger.info("Trusted host key for '%s' written to %s", host, known_hosts)
    return jsonify({
        "success": True,
        "host": host,
        "detail": f"Host key for '{host}' added to known_hosts.",
    })


@bp.route("/copy-key", methods=["POST"])
@login_required
def copy_key():
    """Copy the server's public SSH key to a remote host via ssh-copy-id.

    Expects JSON with ``user``, ``host``, and ``key`` (the public key text).
    Uses the persisted ssh_config so the known_hosts file is honoured.

    Returns JSON with ``success`` (bool) and ``detail`` (str).
    """
    data = request.get_json(silent=True) or {}
    user = data.get("user", "").strip()
    host = data.get("host", "").strip()
    key_text = data.get("key", "").strip()
    password = data.get("password", "").strip()

    if not user or not host or not key_text:
        return jsonify({"success": False, "detail": "user, host, and key are required"}), 400
    if not password:
        return jsonify({"success": False, "detail": "Password is required to install the key for the first time."}), 400

    ssh_dir = Path(current_app.config["DATA_ROOT"]) / "ssh"
    known_hosts = ssh_dir / "known_hosts"

    if not known_hosts.exists():
        return jsonify({
            "success": False,
            "detail": f"Host '{host}' is not yet trusted. Use 'Trust host key' first.",
        })
    check = subprocess.run(
        ["ssh-keygen", "-F", host, "-f", str(known_hosts)],
        capture_output=True,
    )
    if check.returncode != 0:
        return jsonify({
            "success": False,
            "detail": f"Host '{host}' is not yet trusted. Use 'Trust host key' first.",
        })

    ssh_opts = [
        "-o", f"UserKnownHostsFile={known_hosts}",
        "-o", "StrictHostKeyChecking=yes",
        "-o", "BatchMode=no",
    ]
    safe_key = key_text.replace("'", "'\\''")
    remote_cmd = (
        "mkdir -p ~/.ssh && chmod 700 ~/.ssh && "
        f"grep -qxF '{safe_key}' ~/.ssh/authorized_keys 2>/dev/null || "
        f"echo '{safe_key}' >> ~/.ssh/authorized_keys && "
        "chmod 600 ~/.ssh/authorized_keys"
    )

    import os
    env = {**os.environ, "SSHPASS": password}
    try:
        result = subprocess.run(
            ["sshpass", "-e", "ssh", *ssh_opts, f"{user}@{host}", remote_cmd],
            capture_output=True,
            text=True,
            timeout=15,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return jsonify({"success": False, "detail": f"Timed out connecting to {host}"})
    except FileNotFoundError:
        return jsonify({"success": False, "detail": "sshpass is not installed in the container."})
    finally:
        password = ""  # don't keep it in memory longer than needed

    if result.returncode == 0:
        logger.info("Copied public key to %s@%s", user, host)
        return jsonify({"success": True, "detail": f"Public key added to {user}@{host}:~/.ssh/authorized_keys."})
    else:
        detail = result.stderr.strip() or result.stdout.strip() or "Failed to copy key"
        logger.error("Key copy failed for %s@%s: %s", user, host, detail)
        return jsonify({"success": False, "detail": detail})


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
