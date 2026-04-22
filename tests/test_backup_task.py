"""Tests for backup_task.py."""
from pathlib import Path

import pytest

from backup_server.backup_task import BackupTask


def make_task(
    tmp_path: Path,
    src_dir: Path,
    dst_dir: Path,
    runner,
    remote: str = "user@host:/remote",
    excludes: list = None,
) -> BackupTask:
    return BackupTask(
        task={"name": "test-task", "dir_source": str(src_dir), "excludes": excludes or []},
        dir_local=str(dst_dir),
        dir_remote=remote,
        work_dir=tmp_path,
        runner=runner,
    )


# ---------------------------------------------------------------------------
# _write_excludes
# ---------------------------------------------------------------------------

def test_write_excludes_creates_file(work_dir, src_dir, dst_dir, fake_runner):
    task = make_task(work_dir, src_dir, dst_dir, fake_runner(), excludes=["tmp", ".cache"])
    excludes_file = work_dir / "excludes.lst"
    assert excludes_file.exists()
    assert excludes_file.read_text() == "tmp\n.cache"


def test_write_excludes_empty_list(work_dir, src_dir, dst_dir, fake_runner):
    task = make_task(work_dir, src_dir, dst_dir, fake_runner(), excludes=[])
    assert (work_dir / "excludes.lst").read_text() == ""


# ---------------------------------------------------------------------------
# _stderr_has_no_fatal_errors
# ---------------------------------------------------------------------------

def test_stderr_permission_denied_is_not_fatal(work_dir, src_dir, dst_dir, fake_runner):
    task = make_task(work_dir, src_dir, dst_dir, fake_runner())
    result = task._stderr_has_no_fatal_errors(
        "some context: Permission denied (13)"
    )
    assert result is True


def test_stderr_rsync_attrs_warning_is_not_fatal(work_dir, src_dir, dst_dir, fake_runner):
    task = make_task(work_dir, src_dir, dst_dir, fake_runner())
    result = task._stderr_has_no_fatal_errors(
        "rsync error: some files/attrs were not transferred (code 23)"
    )
    assert result is True


def test_stderr_unknown_error_is_fatal(work_dir, src_dir, dst_dir, fake_runner):
    task = make_task(work_dir, src_dir, dst_dir, fake_runner())
    assert task._stderr_has_no_fatal_errors("rsync: connection unexpectedly closed") is False


def test_stderr_empty_string_is_success(work_dir, src_dir, dst_dir, fake_runner):
    task = make_task(work_dir, src_dir, dst_dir, fake_runner())
    assert task._stderr_has_no_fatal_errors("") is True


# ---------------------------------------------------------------------------
# _test_location
# ---------------------------------------------------------------------------

def test_test_location_local_existing_dir(work_dir, src_dir, dst_dir, fake_runner):
    task = make_task(work_dir, src_dir, dst_dir, fake_runner())
    assert task._test_location(str(src_dir)) is True


def test_test_location_local_missing_dir(work_dir, src_dir, dst_dir, fake_runner):
    task = make_task(work_dir, src_dir, dst_dir, fake_runner())
    assert task._test_location("/nonexistent/path/xyz") is False


def test_test_location_remote_delegates_to_host_reachable(work_dir, src_dir, dst_dir, fake_runner):
    # All three subprocess calls (ping, ssh exit, ssh test -d) succeed
    task = make_task(work_dir, src_dir, dst_dir, fake_runner(returncode=0))
    assert task._test_location("user@host:/some/dir") is True


def test_test_location_remote_ping_fails(work_dir, src_dir, dst_dir, fake_runner_sequence):
    runner = fake_runner_sequence([(1, "")])  # ping fails
    task = make_task(work_dir, src_dir, dst_dir, runner)
    assert task._test_location("user@host:/some/dir") is False


def test_test_location_remote_ssh_login_fails(work_dir, src_dir, dst_dir, fake_runner_sequence):
    runner = fake_runner_sequence([(0, ""), (1, "")])  # ping ok, ssh login fails
    task = make_task(work_dir, src_dir, dst_dir, runner)
    assert task._test_location("user@host:/some/dir") is False


def test_test_location_remote_dir_missing(work_dir, src_dir, dst_dir, fake_runner_sequence):
    runner = fake_runner_sequence([
        (0, ""),  # ping
        (0, ""),  # ssh login
        (1, ""),  # dir missing
        (0, ""),  # mkdir succeeds
    ])
    task = make_task(work_dir, src_dir, dst_dir, runner)
    assert task._test_location("user@host:/some/dir") is False


# ---------------------------------------------------------------------------
# _run_step
# ---------------------------------------------------------------------------

def test_run_step_success_appends_to_status(work_dir, src_dir, dst_dir, fake_runner):
    task = make_task(work_dir, src_dir, dst_dir, fake_runner(returncode=0))
    result = task._run_step("backup", ["echo", "hi"], "_backup.log", str(src_dir), str(dst_dir))
    assert result is True
    assert len(task._status["steps"]) == 1
    step = task._status["steps"][0]
    assert step["step"] == "backup"
    assert step["success"] is True


def test_run_step_failure_appends_to_status(work_dir, src_dir, dst_dir, fake_runner):
    task = make_task(work_dir, src_dir, dst_dir, fake_runner(returncode=1))
    result = task._run_step("backup", ["false"], "_backup.log", str(src_dir), str(dst_dir))
    assert result is False
    assert task._status["steps"][0]["success"] is False


def test_run_step_check_stderr_ignores_known_warnings(work_dir, src_dir, dst_dir, fake_runner):
    runner = fake_runner(returncode=1, stderr="some context: Permission denied (13)")
    task = make_task(work_dir, src_dir, dst_dir, runner)
    result = task._run_step(
        "backup", ["false"], "_backup.log", str(src_dir), str(dst_dir), check_stderr=True
    )
    # returncode was 1, but stderr only contains ignorable warnings → success
    assert result is True


def test_run_step_creates_log_file_entry(work_dir, src_dir, dst_dir, fake_runner):
    task = make_task(work_dir, src_dir, dst_dir, fake_runner())
    task._run_step("backup", ["echo"], "_backup.log", str(src_dir))
    assert task._status["steps"][0]["file_log"] == work_dir / "test-task_backup.log"


# ---------------------------------------------------------------------------
# start() — full pipeline
# ---------------------------------------------------------------------------

def test_start_full_success(work_dir, src_dir, dst_dir, fake_runner):
    # ping + ssh-login + ssh-dir + backup + retention + ping + ssh-login + ssh-dir + sync
    # All succeed
    task = make_task(work_dir, src_dir, dst_dir, fake_runner(returncode=0))
    status = task.start()
    assert status["success"] is True
    step_names = [s["step"] for s in status["steps"]]
    assert step_names == ["backup", "retention", "sync"]


def test_start_stops_early_when_local_dirs_unreachable(work_dir, tmp_path, fake_runner):
    # Source dir does not exist → _test_locations_local returns False immediately
    task = BackupTask(
        task={"name": "t", "dir_source": str(tmp_path / "nonexistent"), "excludes": []},
        dir_local=str(tmp_path / "dst"),
        dir_remote="user@host:/remote",
        work_dir=work_dir,
        runner=fake_runner(),
    )
    status = task.start()
    assert status["success"] is False
    assert status["steps"] == []  # no steps were attempted


def test_start_stops_after_backup_failure(work_dir, src_dir, dst_dir, fake_runner_sequence):
    # Local dir checks pass (returncode=0), backup script fails (returncode=1)
    runner = fake_runner_sequence([(1, "fatal error")])  # backup fails
    task = make_task(work_dir, src_dir, dst_dir, runner)
    # Patch location checks to always pass so we reach _backup()
    task._test_locations_local = lambda: True
    status = task.start()
    assert status["success"] is False
    assert len(status["steps"]) == 1
    assert status["steps"][0]["step"] == "backup"
