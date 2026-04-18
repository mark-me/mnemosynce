"""Tests for main.py."""
from pathlib import Path

import pytest

from backup_server.main import delete_logs, main


# ---------------------------------------------------------------------------
# delete_logs
# ---------------------------------------------------------------------------

def test_delete_logs_removes_log_files(tmp_path):
    log_file = tmp_path / "task_backup.log"
    log_file.write_text("log content")
    status = [{"steps": [{"step": "backup", "success": True, "file_log": log_file}]}]
    delete_logs(status)
    assert not log_file.exists()


def test_delete_logs_removes_zip_files(tmp_path):
    log_file = tmp_path / "task_backup.log"
    log_file.write_text("log content")
    zip_file = tmp_path / "task_backup.zip"
    zip_file.write_text("zipped")
    status = [{"steps": [{"step": "backup", "success": True, "file_log": log_file}]}]
    delete_logs(status)
    assert not zip_file.exists()


def test_delete_logs_skips_steps_without_file_log(tmp_path):
    # Steps that were never reached have no file_log key
    status = [{"steps": [{"step": "sync", "success": False, "time_elapsed": "N/A"}]}]
    delete_logs(status)  # should not raise


def test_delete_logs_tolerates_missing_files(tmp_path):
    log_file = tmp_path / "nonexistent.log"
    status = [{"steps": [{"step": "backup", "success": False, "file_log": log_file}]}]
    delete_logs(status)  # should not raise


# ---------------------------------------------------------------------------
# main() — wired together with all dependencies faked
# ---------------------------------------------------------------------------

def test_main_runs_without_real_secrets(minimal_config, tmp_path, fake_runner, monkeypatch):
    """main() should complete without touching nix-sops, SMTP, or real shell scripts."""
    sent = []

    # Patch EmailReport so no SMTP connection is made
    import backup_server.main as main_module
    original_email_report = main_module.EmailReport

    class FakeEmailReport:
        def __init__(self, *args, **kwargs):
            pass
        def send_mail(self, lst_task_status):
            sent.append(lst_task_status)

    monkeypatch.setattr(main_module, "EmailReport", FakeEmailReport)

    # Use a runner that makes all subprocess calls succeed
    monkeypatch.setattr(main_module, "BackupTask",
        lambda task, dir_local, dir_remote: _FakeBackupTask(task))

    main(
        file_config=str(minimal_config),
        password_reader=lambda _: "fake-password",
    )
    assert len(sent) == 1


class _FakeBackupTask:
    """Minimal BackupTask stand-in that returns a successful status immediately."""
    import time as _time

    def __init__(self, task):
        self._name = task["name"]

    def start(self):
        import time
        now = time.time()
        return {
            "name": self._name,
            "success": True,
            "dt_task_start": now - 1,
            "dt_task_end": now,
            "steps": [],
        }


def test_password_reader_called_with_correct_env_var(minimal_config, monkeypatch):
    """main() must request the GMAIL_PASSWORD_FILE env var."""
    requested_vars = []

    import backup_server.main as main_module
    class _FakeEmail:
        def __init__(self, **kw): pass
        def send_mail(self, lst_task_status): pass
    monkeypatch.setattr(main_module, "EmailReport", _FakeEmail)
    monkeypatch.setattr(main_module, "BackupTask", lambda **kw: _FakeBackupTask({"name": "t"}))

    def capturing_reader(env_var):
        requested_vars.append(env_var)
        return "fake-password"

    main(file_config=str(minimal_config), password_reader=capturing_reader)
    assert "GMAIL_PASSWORD_FILE" in requested_vars
