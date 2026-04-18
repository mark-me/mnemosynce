"""Read-only queries against log.db for the dashboard.

All functions accept a db_path (Path) and return plain dicts/lists so
the routes stay thin and the data layer is independently testable.

Schema (from database.py):
    task_run (
        id_task, dt_task_start, dt_task_end, success_task,
        id_step, dt_step_start, dt_step_end, success_step,
        dir_from, dir_to, time_elapsed
    )

A "run" is the set of rows that share the same (id_task, dt_task_start).
A run is considered successful when ALL its step rows have success_step = 1.
"""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path


def _connect(db_path: Path) -> sqlite3.Connection:
    """Open a SQLite connection to the dashboard database with row dict access.

    This helper centralises connection creation so all queries share the same
    row factory configuration and can access columns by name.

    Args:
        db_path (Path): Filesystem path to the SQLite database file.

    Returns:
        sqlite3.Connection: An open connection configured with Row objects.
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _ts(unix: float | None) -> str:
    """Convert a Unix timestamp into a human-readable UTC display string.

    This formats timestamps for use in the dashboard views and returns a
    placeholder when no timestamp is available.

    Args:
        unix (float | None): The Unix timestamp in seconds, or None if missing.

    Returns:
        str: A formatted ``YYYY-MM-DD HH:MM UTC`` string, or ``"—"`` when no value is provided.
    """
    if unix is None:
        return "—"
    return datetime.fromtimestamp(unix, tz=UTC).strftime("%Y-%m-%d %H:%M UTC")


def get_summary(db_path: Path) -> dict:
    """Summarise overall backup run history across all tasks.

    This reports how many runs have been recorded, how many succeeded
    or failed, which tasks have run, and when the most recent run started.

    Args:
        db_path (Path): Filesystem path to the SQLite dashboard database.

    Returns:
        dict: A summary dictionary with keys ``total_runs``, ``successful_runs``,
        ``failed_runs``, ``tasks``, and ``last_run_ts``.
    """
    if not db_path.exists():
        return {
            "total_runs": 0,
            "successful_runs": 0,
            "failed_runs": 0,
            "tasks": [],
            "last_run_ts": "—",
        }

    with _connect(db_path) as conn:
        rows = conn.execute("""
            SELECT
                id_task,
                dt_task_start,
                COUNT(*)            AS step_count,
                SUM(success_step)   AS ok_steps
            FROM task_run
            GROUP BY id_task, dt_task_start
        """).fetchall()

    total = len(rows)
    successful = sum(r["step_count"] == r["ok_steps"] for r in rows)
    tasks = sorted({r["id_task"] for r in rows})
    last_ts = max((r["dt_task_start"] for r in rows), default=None)

    return {
        "total_runs": total,
        "successful_runs": successful,
        "failed_runs": total - successful,
        "tasks": tasks,
        "last_run_ts": _ts(last_ts),
    }


def get_task_history(db_path: Path, task_name: str | None = None, limit: int = 50) -> list[dict]:
    """Return recent run history and step details for a given task.

    This fetches the most recent runs from the dashboard database, aggregating
    per-run success and timing information along with a breakdown of individual steps.

    Args:
        db_path (Path): Filesystem path to the SQLite dashboard database.
        task_name (str | None): Optional task identifier to filter runs; when None, all tasks are included.
        limit (int): Maximum number of runs to return, ordered from most recent first.

    Returns:
        list[dict]: A list of run dictionaries, each containing task metadata, timing,
        overall success, and a nested ``steps`` list describing each step in the run.
    """
    if not db_path.exists():
        return []

    run_rows, step_rows = _fetch_run_and_step_rows(db_path, task_name, limit)
    if not run_rows:
        return []

    steps_by_run = _index_steps_by_run(step_rows)

    runs: list[dict] = []
    for r in run_rows:
        key = (r["id_task"], r["dt_task_start"])
        success = r["step_count"] == r["ok_steps"]
        elapsed_secs = (r["dt_task_end"] or r["dt_task_start"]) - r["dt_task_start"]
        h, rem = divmod(int(elapsed_secs), 3600)
        m, s = divmod(rem, 60)
        runs.append(
            {
                "task": r["id_task"],
                "started": _ts(r["dt_task_start"]),
                "ended": _ts(r["dt_task_end"]),
                "elapsed": f"{h:02d}:{m:02d}:{s:02d}",
                "success": success,
                "steps": steps_by_run.get(key, []),
            }
        )
    return runs


def _fetch_run_and_step_rows(
    db_path: Path, task_name: str | None, limit: int
) -> tuple[list[sqlite3.Row], list[sqlite3.Row]]:
    """Fetch aggregated run rows and per-step rows for the requested history query.

    This applies the optional task filter and row limit, returning both per-run
    summary rows and the underlying step rows used to build the task history.

    Args:
        db_path (Path): Filesystem path to the SQLite dashboard database.
        task_name (str | None): Optional task identifier to filter runs; when None, all tasks are included.
        limit (int): Maximum number of runs to fetch when aggregating history.

    Returns:
        tuple[list[sqlite3.Row], list[sqlite3.Row]]: A pair of row lists containing
        the aggregated run rows and their corresponding step rows.
    """
    where = "WHERE id_task = ?" if task_name else ""
    params: tuple[object, ...] = (task_name,) if task_name else ()

    with _connect(db_path) as conn:
        run_rows = conn.execute(
            f"""
            SELECT
                id_task,
                dt_task_start,
                dt_task_end,
                COUNT(*)            AS step_count,
                SUM(success_step)   AS ok_steps,
                MIN(success_task)   AS success_task
            FROM task_run
            {where}
            GROUP BY id_task, dt_task_start
            ORDER BY dt_task_start DESC
            LIMIT ?
        """,
            (*params, limit),
        ).fetchall()

        if not run_rows:
            return [], []

        placeholders = ",".join("?" * len(run_rows))
        starts = [r["dt_task_start"] for r in run_rows]
        step_rows = conn.execute(
            f"""
            SELECT id_task, dt_task_start, id_step,
                    dt_step_start, dt_step_end,
                    success_step, dir_from, dir_to, time_elapsed
            FROM task_run
            WHERE dt_task_start IN ({placeholders})
            ORDER BY dt_task_start DESC, dt_step_start ASC
        """,
            starts,
        ).fetchall()

    return list(run_rows), list(step_rows)


def _index_steps_by_run(step_rows: list[sqlite3.Row]) -> dict[tuple[object, object], list[dict]]:
    """Group step rows by (task, run start) key for quick lookup when building runs.

    This prepares a mapping from each run to its ordered list of step dictionaries,
    ready to be embedded in the final task history response.

    Args:
        step_rows (list[sqlite3.Row]): The raw step rows fetched from the database.

    Returns:
        dict[tuple[object, object], list[dict]]: A mapping from ``(id_task, dt_task_start)``
        to an ordered list of step detail dictionaries.
    """
    steps_by_run: dict[tuple[object, object], list[dict]] = {}
    for s in step_rows:
        key = (s["id_task"], s["dt_task_start"])
        steps_by_run.setdefault(key, []).append(
            {
                "step": s["id_step"],
                "success": bool(s["success_step"]),
                "started": _ts(s["dt_step_start"]),
                "elapsed": s["time_elapsed"] or "—",
                "dir_from": s["dir_from"] or "—",
                "dir_to": s["dir_to"] or "—",
            }
        )
    return steps_by_run


def get_task_stats(db_path: Path) -> list[dict]:
    """Return per-task aggregate statistics derived from the run history.

    This reports how many times each task has run, how many runs succeeded
    or failed, the success rate, and when the task last executed.

    Args:
        db_path (Path): Filesystem path to the SQLite dashboard database.

    Returns:
        list[dict]: A list of task summary dictionaries with counts and timing.
    """
    if not db_path.exists():
        return []

    with _connect(db_path) as conn:
        rows = conn.execute("""
            SELECT
                id_task,
                COUNT(DISTINCT dt_task_start)   AS total_runs,
                MAX(dt_task_start)              AS last_run,
                SUM(CASE WHEN step_count = ok_steps THEN 1 ELSE 0 END) AS successes
            FROM (
                SELECT
                    id_task,
                    dt_task_start,
                    COUNT(*)          AS step_count,
                    SUM(success_step) AS ok_steps
                FROM task_run
                GROUP BY id_task, dt_task_start
            )
            GROUP BY id_task
            ORDER BY id_task
        """).fetchall()

    stats = []
    for r in rows:
        total = r["total_runs"]
        succ = r["successes"]
        stats.append(
            {
                "task": r["id_task"],
                "total_runs": total,
                "successful": succ,
                "failed": total - succ,
                "success_rate": round(100 * succ / total) if total else 0,
                "last_run_ts": _ts(r["last_run"]),
            }
        )
    return stats
