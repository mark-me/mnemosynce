"""Tests for web.setup_state and the setup wizard routes.

Covers:

- ``get_setup_status`` — each check isolated (config, ssh_key, schedule,
  connection, remote-source detection)
- ``is_setup_complete`` — both automatic (all-checks) and explicit (session
  flag) completion paths
- ``setup_complete_required`` decorator — redirect behaviour when setup is
  incomplete vs. complete
- Wizard routes — HTTP status codes, step-skipping when no remote sources,
  explicit finish endpoint

All tests run against the Flask test client in ``TestConfig`` mode (debug on,
login bypassed, isolated temp paths), so no real filesystem, SSH, or SMTP
calls are made.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from config.config import TestConfig
from web.app import create_app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def app(tmp_path):
    """Create a Flask test-app with isolated data directories.

    Args:
        tmp_path: pytest-provided temporary directory, unique per test.

    Yields:
        Flask: A configured application instance in testing mode.
    """
    cfg = TestConfig()
    cfg.DATA_ROOT = tmp_path
    cfg.CONFIG_PATH = tmp_path / "backup_config.yml"
    cfg.DB_PATH = tmp_path / "log.db"
    cfg.SSH_KEY_DIR = tmp_path / "ssh"
    cfg.SSH_KEY_DIR.mkdir(parents=True, exist_ok=True)
    yield create_app(cfg)


@pytest.fixture()
def client(app):
    """Return a Flask test client with a fresh session context.

    Args:
        app: The Flask application fixture.

    Returns:
        FlaskClient: A test client for making HTTP requests.
    """
    return app.test_client()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_config(app, remote: bool = True) -> None:
    """Write a minimal valid backup_config.yml.

    Args:
        app: The Flask application instance (provides CONFIG_PATH).
        remote (bool): When True the task source uses an SSH address so
            ``has_remote_sources`` returns True.  When False a local path
            is used instead.
    """
    source = "user@host:/data" if remote else "/data"
    cfg = {
        "dir_backup_local": "/mnt/local",
        "dir_backup_remote": "user@host:/mnt/remote",
        "email_sender": "a@gmail.com",
        "email_report": "b@example.com",
        "tasks": [{"name": "T", "dir_source": source}],
    }
    Path(app.config["CONFIG_PATH"]).write_text(
        yaml.dump(cfg), encoding="utf-8"
    )


def _write_ssh_key(app, name: str = "test_key") -> None:
    """Create a stub ed25519 keypair in SSH_KEY_DIR.

    Args:
        app: The Flask application instance (provides SSH_KEY_DIR).
        name (str): Base name for the key files.
    """
    ssh_dir = Path(app.config["SSH_KEY_DIR"])
    (ssh_dir / name).write_text("PRIVATE", encoding="utf-8")
    (ssh_dir / f"{name}.pub").write_text("ssh-ed25519 AAAA test", encoding="utf-8")


def _write_schedule(app, enabled: bool = True) -> None:
    """Write a schedule.json file to DATA_ROOT.

    Args:
        app: The Flask application instance (provides DATA_ROOT).
        enabled (bool): Whether the schedule is active.
    """
    schedule_path = Path(app.config["DATA_ROOT"]) / "schedule.json"
    schedule_path.write_text(
        json.dumps({"cron": "0 2 * * *", "enabled": enabled}),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# get_setup_status — individual checks
# ---------------------------------------------------------------------------


class TestGetSetupStatus:
    """Unit tests for each check inside get_setup_status."""

    def test_all_false_when_data_root_empty(self, app, client):
        """All checks are False when no files exist at all."""
        with client.session_transaction() as sess:
            sess.clear()
        with app.test_request_context():
            from web.setup_state import get_setup_status
            status = get_setup_status(app)
        assert status["config"] is False
        assert status["ssh_key"] is True   # no remote sources → auto-True
        assert status["connection"] is True
        assert status["schedule"] is False
        assert status["complete"] is False
        assert status["has_remote_sources"] is False

    def test_config_true_when_valid_file_exists(self, app, client):
        """config check passes when the YAML file is valid."""
        _write_config(app, remote=False)
        with app.test_request_context():
            from web.setup_state import get_setup_status
            status = get_setup_status(app)
        assert status["config"] is True

    def test_config_false_for_incomplete_yaml(self, app, client):
        """config check fails when required keys are missing."""
        Path(app.config["CONFIG_PATH"]).write_text(
            "dir_backup_local: /mnt\n", encoding="utf-8"
        )
        with app.test_request_context():
            from web.setup_state import get_setup_status
            status = get_setup_status(app)
        assert status["config"] is False

    def test_ssh_key_true_when_keypair_exists(self, app, client):
        """ssh_key check passes when at least one complete keypair is present."""
        _write_config(app, remote=True)
        _write_ssh_key(app)
        with app.test_request_context():
            from web.setup_state import get_setup_status
            status = get_setup_status(app)
        assert status["ssh_key"] is True
        assert status["has_remote_sources"] is True

    def test_ssh_key_false_when_only_pub_exists(self, app, client):
        """ssh_key check fails when the private key file is missing."""
        _write_config(app, remote=True)
        ssh_dir = Path(app.config["SSH_KEY_DIR"])
        (ssh_dir / "test_key.pub").write_text("ssh-ed25519 AAAA", encoding="utf-8")
        with app.test_request_context():
            from web.setup_state import get_setup_status
            status = get_setup_status(app)
        assert status["ssh_key"] is False

    def test_ssh_key_auto_true_when_no_remote_sources(self, app, client):
        """ssh_key is automatically satisfied when config has only local sources."""
        _write_config(app, remote=False)
        with app.test_request_context():
            from web.setup_state import get_setup_status
            status = get_setup_status(app)
        assert status["has_remote_sources"] is False
        assert status["ssh_key"] is True

    def test_connection_true_when_session_flag_set(self, app, client):
        """connection check passes when setup_connection_tested is in the session."""
        _write_config(app, remote=True)
        with client.session_transaction() as sess:
            sess["setup_connection_tested"] = True
        with app.test_request_context(environ_base={"HTTP_COOKIE": ""}):
            # Simulate the session flag being set
            from flask import session as flask_session
            from web.setup_state import get_setup_status
            # Use the client's session via a real request
        response = client.get("/setup/connections")
        # Just checking the route responds; connection flag tested via session below
        with client as c:
            with c.session_transaction() as sess:
                sess["setup_connection_tested"] = True
            with app.test_request_context():
                from web.setup_state import _connection_tested
                from flask import session
                session["setup_connection_tested"] = True
                assert _connection_tested() is True

    def test_schedule_true_when_enabled(self, app, client):
        """schedule check passes when schedule.json exists and is enabled."""
        _write_schedule(app, enabled=True)
        with app.test_request_context():
            from web.setup_state import get_setup_status
            status = get_setup_status(app)
        assert status["schedule"] is True

    def test_schedule_false_when_disabled(self, app, client):
        """schedule check fails when schedule.json exists but enabled is False."""
        _write_schedule(app, enabled=False)
        with app.test_request_context():
            from web.setup_state import get_setup_status
            status = get_setup_status(app)
        assert status["schedule"] is False

    def test_schedule_false_when_file_absent(self, app, client):
        """schedule check fails when schedule.json does not exist."""
        with app.test_request_context():
            from web.setup_state import get_setup_status
            status = get_setup_status(app)
        assert status["schedule"] is False


# ---------------------------------------------------------------------------
# is_setup_complete — completion paths
# ---------------------------------------------------------------------------


class TestIsSetupComplete:
    """Tests for both completion paths: automatic and explicit."""

    def test_complete_when_all_checks_pass_no_remote(self, app, client):
        """Setup completes automatically when all filesystem checks pass (local only)."""
        _write_config(app, remote=False)
        _write_schedule(app)
        with app.test_request_context():
            from web.setup_state import is_setup_complete
            assert is_setup_complete(app) is True

    def test_complete_when_all_checks_pass_with_remote(self, app, client):
        """Setup completes automatically when all checks pass including SSH/connection."""
        _write_config(app, remote=True)
        _write_ssh_key(app)
        _write_schedule(app)
        with app.test_request_context():
            from flask import session
            session["setup_connection_tested"] = True
            from web.setup_state import is_setup_complete
            assert is_setup_complete(app) is True

    def test_complete_via_explicit_flag_ignores_incomplete_checks(self, app, client):
        """Explicit session flag marks setup complete even if checks are still failing."""
        # No config, no keys, no schedule — but explicit flag set
        with app.test_request_context():
            from flask import session
            session["setup_explicitly_complete"] = True
            from web.setup_state import is_setup_complete
            assert is_setup_complete(app) is True

    def test_incomplete_when_schedule_missing(self, app, client):
        """Setup is not complete when schedule check fails (no explicit flag)."""
        _write_config(app, remote=False)
        # No schedule
        with app.test_request_context():
            from web.setup_state import is_setup_complete
            assert is_setup_complete(app) is False

    def test_mark_setup_complete_sets_session_flag(self, app, client):
        """mark_setup_complete() sets setup_explicitly_complete in the session."""
        with app.test_request_context():
            from flask import session
            from web.setup_state import mark_setup_complete
            mark_setup_complete()
            assert session.get("setup_explicitly_complete") is True

    def test_mark_connection_tested_sets_session_flag(self, app, client):
        """mark_connection_tested() sets setup_connection_tested in the session."""
        with app.test_request_context():
            from flask import session
            from web.setup_state import mark_connection_tested
            mark_connection_tested()
            assert session.get("setup_connection_tested") is True


# ---------------------------------------------------------------------------
# setup_complete_required decorator
# ---------------------------------------------------------------------------


class TestSetupCompleteRequired:
    """Tests for the redirect-to-wizard decorator."""

    def test_redirects_to_setup_when_incomplete(self, app, client):
        """Dashboard redirects to /setup/ when setup is not complete."""
        # No config, no schedule — setup is incomplete
        response = client.get("/dashboard/", follow_redirects=False)
        assert response.status_code == 302
        assert "/setup/" in response.headers["Location"]

    def test_allows_access_when_complete(self, app, client):
        """Dashboard is accessible after all checks pass."""
        _write_config(app, remote=False)
        _write_schedule(app)
        response = client.get("/dashboard/", follow_redirects=False)
        assert response.status_code == 200

    def test_progress_redirects_when_incomplete(self, app, client):
        """Progress page redirects to /setup/ when setup is not complete."""
        response = client.get("/progress/", follow_redirects=False)
        assert response.status_code == 302
        assert "/setup/" in response.headers["Location"]

    def test_schedule_run_now_blocked_when_incomplete(self, app, client):
        """Run-now endpoint redirects to /setup/ when setup is not complete."""
        response = client.post("/schedule/run-now", follow_redirects=False)
        assert response.status_code == 302
        assert "/setup/" in response.headers["Location"]


# ---------------------------------------------------------------------------
# Wizard routes
# ---------------------------------------------------------------------------


class TestWizardRoutes:
    """HTTP-level tests for the setup wizard blueprint."""

    def test_setup_index_redirects_to_first_incomplete_step(self, app, client):
        """/setup/ forwards to the config step when nothing is done."""
        response = client.get("/setup/", follow_redirects=False)
        assert response.status_code == 302
        assert "config" in response.headers["Location"]

    def test_setup_index_redirects_to_dashboard_when_complete(self, app, client):
        """/setup/ forwards to dashboard when all checks pass."""
        _write_config(app, remote=False)
        _write_schedule(app)
        response = client.get("/setup/", follow_redirects=False)
        assert response.status_code == 302
        assert "dashboard" in response.headers["Location"]

    def test_step_config_renders(self, app, client):
        """The config step page returns 200 with a YAML editor."""
        response = client.get("/setup/config")
        assert response.status_code == 200
        assert b"backup_config.yml" in response.data

    def test_step_ssh_keys_skipped_for_local_only_config(self, app, client):
        """SSH key step redirects to schedule when no remote sources are configured."""
        _write_config(app, remote=False)
        response = client.get("/setup/ssh-keys", follow_redirects=False)
        assert response.status_code == 302
        assert "schedule" in response.headers["Location"]

    def test_step_connections_skipped_for_local_only_config(self, app, client):
        """Connections step redirects to schedule when no remote sources are configured."""
        _write_config(app, remote=False)
        response = client.get("/setup/connections", follow_redirects=False)
        assert response.status_code == 302
        assert "schedule" in response.headers["Location"]

    def test_step_ssh_keys_shown_for_remote_config(self, app, client):
        """SSH key step renders normally when config has a remote source."""
        _write_config(app, remote=True)
        response = client.get("/setup/ssh-keys")
        assert response.status_code == 200
        assert b"Generate" in response.data

    def test_step_connections_shown_for_remote_config(self, app, client):
        """Connections step renders normally when config has a remote source."""
        _write_config(app, remote=True)
        response = client.get("/setup/connections")
        assert response.status_code == 200
        assert b"SSH Connection" in response.data

    def test_step_schedule_renders(self, app, client):
        """The schedule step page returns 200."""
        response = client.get("/setup/schedule")
        assert response.status_code == 200
        assert b"Finish setup" in response.data

    def test_finish_sets_session_flag_and_redirects(self, app, client):
        """POST /setup/complete sets the explicit flag and redirects to dashboard."""
        response = client.post("/setup/complete", follow_redirects=False)
        assert response.status_code == 302
        assert "dashboard" in response.headers["Location"]
        # After the redirect the explicit flag must be set
        with client.session_transaction() as sess:
            assert sess.get("setup_explicitly_complete") is True

    def test_dashboard_accessible_after_explicit_finish(self, app, client):
        """Dashboard is accessible immediately after the finish endpoint is called."""
        client.post("/setup/complete")
        response = client.get("/dashboard/")
        assert response.status_code == 200

    def test_all_checks_pass_banner_shown_on_schedule_step(self, app, client):
        """The 'all checks passed' banner appears when filesystem checks are satisfied."""
        _write_config(app, remote=False)
        _write_schedule(app)
        response = client.get("/setup/schedule")
        assert response.status_code == 200
        assert b"All checks passed" in response.data

    def test_finish_anyway_shown_when_checks_incomplete(self, app, client):
        """'Finish setup anyway' text is shown when not all checks pass yet."""
        response = client.get("/setup/schedule")
        assert response.status_code == 200
        assert b"Finish setup anyway" in response.data
