import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)


class LogDB:
    """Storing all back-up run results to enable more prescriptive emails to the users"""

    def __init__(self, file_db: str):
        """Initializes a log database

        Args:
            file_db (str): The file that represents the database
        """
        self._file_db = file_db
        Path(file_db).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(file_db)
        self._create_tables()

    def close(self) -> None:
        """Close the database connection. Call when done to avoid resource warnings."""
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def _create_tables(self) -> None:
        """Creates tables in the database if they don't exist"""
        cursor = self.db.cursor()
        cursor.execute(
            """CREATE TABLE IF NOT EXISTS task_run
            (   id_task         TEXT,
                dt_task_start   REAL,
                dt_task_end     REAL,
                success_task    INTEGER,
                id_step         TEXT,
                dt_step_start   REAL,
                dt_step_end     REAL,
                success_step    INTEGER,
                dir_from        TEXT,
                dir_to          TEXT,
                time_elapsed    TEXT,
                skip_reason     TEXT
                )"""
        )
        self.db.commit()

    def _migrate(self) -> None:
        """Add columns introduced after initial release without dropping existing data."""
        cursor = self.db.cursor()
        existing = {row[1] for row in cursor.execute("PRAGMA table_info(task_run)")}
        if "skip_reason" not in existing:
            cursor.execute("ALTER TABLE task_run ADD COLUMN skip_reason TEXT")
            self.db.commit()
        self._migrate()

    def add_task_run(self, task_status: dict) -> None:
        """Store task run results

        Args:
            task_status (dict): Contains all information for a task run and its steps
        """
        logger.info(
            f"Storing run information of '{task_status['name']}' to '{self._file_db}'"
        )
        cursor = self.db.cursor()
        for step in task_status["steps"]:
            cursor.execute(
                "INSERT INTO task_run VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    task_status["name"],
                    task_status["dt_task_start"],
                    task_status["dt_task_end"],
                    task_status["success"],
                    step["step"],
                    step["dt_start"],
                    step["dt_end"],
                    step["success"],
                    step.get("dir_from", ""),
                    step.get("dir_to", ""),
                    step.get("time_elapsed", ""),
                    step.get("skip_reason", None),
                ),
            )
        self.db.commit()

    def get_tasks_last_success(self) -> dict:
        """Retrieve the last time a task run has successfully completed

        Returns:
            dict: Each task in the database and the last time it ran successfully.
        """
        cursor = self.db.cursor()
        cursor.execute(
            """
            SELECT
                id_task,
                MAX(dt_step_start)
            FROM
                (
                    SELECT
                        id_task,
                        dt_step_start
                    FROM
                        task_run
                    GROUP BY
                        id_task,
                        dt_step_start
                    HAVING
                        COUNT(*) = SUM(success_step)
                )
            GROUP BY
                id_task
            """
        )
        return dict(cursor.fetchall())
