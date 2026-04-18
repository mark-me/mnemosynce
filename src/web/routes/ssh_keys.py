"""SSH key management routes.

    GET  /ssh-keys/          — show existing keys and generation form
    POST /ssh-keys/generate  — generate a new ed25519 keypair
    POST /ssh-keys/delete    — delete an existing keypair

Keys are stored in DATA_ROOT/ssh/. Each keypair is stored as:
    <name>          (private key, chmod 600)
    <name>.pub      (public key)

The private key never leaves the server. The public key is displayed
so the user can copy it to the remote host's authorized_keys.
"""

import logging
import subprocess
from pathlib import Path

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from web.auth import login_required

logger = logging.getLogger(__name__)

bp = Blueprint("ssh_keys", __name__, url_prefix="/ssh-keys")


def _ssh_dir() -> Path:
    return current_app.config["SSH_KEY_DIR"]


def _list_keys() -> list:
    """Return a list of dicts describing each keypair in SSH_KEY_DIR."""
    ssh_dir = _ssh_dir()
    keys = []
    for pub in sorted(ssh_dir.glob("*.pub")):
        private = pub.with_suffix("")
        keys.append(
            {
                "name": private.name,
                "public_key": pub.read_text(encoding="utf-8").strip(),
                "has_private": private.exists(),
            }
        )
    return keys


@bp.route("/")
@login_required
def index():
    return render_template("web/ssh_keys.html", keys=_list_keys())


@bp.route("/generate", methods=["POST"])
@login_required
def generate():
    name = request.form.get("name", "").strip()

    if not name:
        flash("Key name is required.", "danger")
        return redirect(url_for("ssh_keys.index"))

    # Reject names with path separators or shell-unsafe characters
    if any(c in name for c in "/\\. \t\n"):
        flash("Key name must not contain spaces, dots, or path separators.", "danger")
        return redirect(url_for("ssh_keys.index"))

    ssh_dir = _ssh_dir()
    key_path = ssh_dir / name

    if key_path.exists() or (ssh_dir / f"{name}.pub").exists():
        flash(f"A key named '{name}' already exists. Delete it first.", "warning")
        return redirect(url_for("ssh_keys.index"))

    comment = request.form.get("comment", f"backup-server/{name}").strip()

    result = subprocess.run(
        [
            "ssh-keygen",
            "-t",
            "ed25519",
            "-f",
            str(key_path),
            "-C",
            comment,
            "-N",
            "",  # no passphrase
            "-q",
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        logger.error("ssh-keygen failed: %s", result.stderr)
        flash(f"Key generation failed: {result.stderr.strip()}", "danger")
        return redirect(url_for("ssh_keys.index"))

    # Ensure private key is readable only by owner
    key_path.chmod(0o600)

    flash(f"Key '{name}' generated successfully.", "success")
    return redirect(url_for("ssh_keys.index"))


@bp.route("/delete", methods=["POST"])
@login_required
def delete():
    name = request.form.get("name", "").strip()
    if not name:
        flash("No key name provided.", "danger")
        return redirect(url_for("ssh_keys.index"))

    ssh_dir = _ssh_dir()
    deleted = []
    for path in [ssh_dir / name, ssh_dir / f"{name}.pub"]:
        if path.exists():
            path.unlink()
            deleted.append(path.name)

    if deleted:
        flash(f"Deleted: {', '.join(deleted)}", "success")
    else:
        flash(f"No files found for key '{name}'.", "warning")

    return redirect(url_for("ssh_keys.index"))
