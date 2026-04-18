"""Shared test helper functions (not fixtures — those stay in conftest.py)."""
import time
from pathlib import Path


def make_step(name: str, success: bool, file_log: Path = None) -> dict:
    now = time.time()
    step = {
        "step": name,
        "dir_from": "/src",
        "dir_to": "/dst",
        "success": success,
        "dt_start": now - 1,
        "dt_end": now,
        "time_elapsed": "00:00:01",
    }
    if file_log:
        step["file_log"] = file_log
    return step


def make_task_status(
    name: str = "test-task",
    success: bool = True,
    steps: list = None,
) -> dict:
    now = time.time()
    if steps is None:
        steps = [
            make_step("backup", success),
            make_step("retention", success),
            make_step("sync", success),
        ]
    return {
        "name": name,
        "success": success,
        "dt_task_start": now - 10,
        "dt_task_end": now,
        "steps": steps,
    }
