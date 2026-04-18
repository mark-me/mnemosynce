"""Shared fixtures for the backup-server test suite."""
import subprocess
from pathlib import Path

import pytest
import yaml

from backup_server.database import LogDB
from tests.helpers import make_step, make_task_status


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

@pytest.fixture
def db() -> LogDB:
    """In-memory SQLite database — fast, isolated, no file cleanup needed."""
    with LogDB(":memory:") as database:
        yield database


# ---------------------------------------------------------------------------
# Subprocess faking
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_runner():
    """Factory that returns a subprocess.run-compatible callable."""
    def make(returncode: int = 0, stderr: str = "", stdout: str = "") -> callable:
        def runner(cmd, **kwargs):
            return subprocess.CompletedProcess(
                args=cmd, returncode=returncode, stdout=stdout, stderr=stderr
            )
        return runner
    return make


@pytest.fixture
def fake_runner_sequence():
    """Factory for a runner that returns different results on successive calls."""
    def make(results: list[tuple[int, str]]) -> callable:
        calls = iter(results)
        def runner(cmd, **kwargs):
            returncode, stderr = next(calls)
            return subprocess.CompletedProcess(
                args=cmd, returncode=returncode, stdout="", stderr=stderr
            )
        return runner
    return make


# ---------------------------------------------------------------------------
# Filesystem helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def work_dir(tmp_path: Path) -> Path:
    """A tmp_path pre-populated with dummy shell scripts."""
    for name in ("backup.sh", "delete_old_backups.sh", "sync_backup_to_remote.sh"):
        (tmp_path / name).write_text("#!/bin/sh\n")
    return tmp_path


@pytest.fixture
def src_dir(tmp_path: Path) -> Path:
    """A source directory that actually exists on disk."""
    d = tmp_path / "source"
    d.mkdir()
    return d


@pytest.fixture
def dst_dir(tmp_path: Path) -> Path:
    """A local backup destination directory that actually exists on disk."""
    d = tmp_path / "destination"
    d.mkdir()
    return d


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def minimal_config(tmp_path: Path, src_dir: Path, dst_dir: Path) -> Path:
    """Write a minimal valid YAML config file and return its path."""
    config = {
        "dir_backup_local": str(dst_dir),
        "dir_backup_remote": "user@host:/remote",
        "email_sender": "sender@example.com",
        "email_report": "report@example.com",
        "email_admin": "",
        "tasks": [
            {
                "name": "test-task",
                "dir_source": str(src_dir),
                "excludes": ["tmp", ".cache"],
            }
        ],
    }
    config_file = tmp_path / "config.yml"
    config_file.write_text(yaml.dump(config), encoding="utf-8")
    return config_file
