"""Tests for database.py — all use an in-memory SQLite DB."""
import time

import pytest

from backup_server.database import LogDB
from tests.conftest import make_task_status, make_step


def test_creates_tables(db: LogDB):
    cursor = db.db.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='task_run'")
    assert cursor.fetchone() is not None


def test_add_task_run_stores_rows(db: LogDB):
    status = make_task_status(name="photos", success=True)
    db.add_task_run(status)

    cursor = db.db.cursor()
    cursor.execute("SELECT id_task, success_task FROM task_run")
    rows = cursor.fetchall()
    assert len(rows) == 3  # one row per step
    assert all(row[0] == "photos" for row in rows)
    assert all(row[1] == 1 for row in rows)


def test_add_task_run_failed(db: LogDB):
    status = make_task_status(name="docs", success=False)
    db.add_task_run(status)

    cursor = db.db.cursor()
    cursor.execute("SELECT success_task FROM task_run WHERE id_task='docs'")
    assert all(row[0] == 0 for row in cursor.fetchall())


def test_get_tasks_last_success_empty(db: LogDB):
    assert db.get_tasks_last_success() == {}


def test_get_tasks_last_success_returns_latest(db: LogDB):
    now = time.time()
    # Two successful runs for the same task — should return the later one
    early = make_task_status("photos", success=True)
    early["dt_task_start"] = now - 200
    early["dt_task_end"] = now - 100
    for s in early["steps"]:
        s["dt_start"] = now - 200
        s["dt_end"] = now - 100

    late = make_task_status("photos", success=True)
    late["dt_task_start"] = now - 50
    late["dt_task_end"] = now - 10
    for s in late["steps"]:
        s["dt_start"] = now - 50
        s["dt_end"] = now - 10

    db.add_task_run(early)
    db.add_task_run(late)

    result = db.get_tasks_last_success()
    assert "photos" in result
    assert result["photos"] == pytest.approx(late["steps"][0]["dt_start"], rel=1e-3)


def test_get_tasks_last_success_ignores_failed(db: LogDB):
    status = make_task_status("docs", success=False)
    db.add_task_run(status)
    assert db.get_tasks_last_success() == {}


def test_add_task_run_with_paths_containing_quotes(db: LogDB):
    """Parameterised queries must handle paths with single quotes."""
    status = make_task_status(name="it's-a-task", success=True)
    status["steps"][0]["dir_from"] = "/home/user/it's a folder"
    db.add_task_run(status)  # would crash with f-string SQL injection

    cursor = db.db.cursor()
    cursor.execute("SELECT id_task FROM task_run")
    assert cursor.fetchone()[0] == "it's-a-task"
