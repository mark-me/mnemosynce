import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def delete_logs(lst_task_status: list) -> None:
    """Remove shell-script log files (and their zipped copies) produced during a run.

    Args:
        lst_task_status: Task run statuses returned by BackupTask.start()
    """
    log_files = [
        step["file_log"]
        for task in lst_task_status
        for step in task["steps"]
        if "file_log" in step
    ]
    for file_log in log_files:
        if file_log.exists():
            file_log.unlink()
        file_zip = file_log.with_suffix(".zip")
        if file_zip.exists():
            file_zip.unlink()
    app_zip = Path("log.zip")
    if app_zip.exists():
        app_zip.unlink()
