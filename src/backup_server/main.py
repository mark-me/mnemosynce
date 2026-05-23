import argparse
import logging
import os
import tempfile
from collections.abc import Callable
from pathlib import Path

from config import get_config

from .backup_task import BackupTask
from .config_file import ConfigFile
from .database import LogDB
from .email_report import EmailReport
from .logging_config import setup_logging

logger = logging.getLogger(__name__)


def _read_password(env_var: str) -> str:
    """Read a password from the file pointed to by an environment variable.

    Args:
        env_var (str): Name of the environment variable holding the file path.

    Returns:
        str: The password string.
    """
    if password_file := os.environ.get(env_var):
        return Path(password_file).read_text(encoding="utf-8").strip()
    else:
        raise OSError(f"Environment variable '{env_var}' is not set.")


def delete_logs(lst_task_status: list) -> None:
    """Remove step log files and their zipped equivalents after the email is sent.

    Args:
        lst_task_status (list): Task run statuses.
    """
    for task in lst_task_status:
        for step in task["steps"]:
            if "file_log" not in step:
                continue
            file_log: Path = step["file_log"]
            if file_log.exists():
                file_log.unlink()
            file_zip = file_log.parent / f"{file_log.stem}.zip"
            if file_zip.exists():
                file_zip.unlink()
    for leftover in [Path("log.zip"), Path("log.json.zip")]:
        if leftover.exists():
            leftover.unlink()


def _capture_run_log(log_path: Path, start_pos: int) -> Path:
    """Extract log entries written since start_pos into a temporary file.

    Returns a NamedTemporaryFile path containing only this run's log lines.
    The caller is responsible for deleting it after the email is sent.
    """
    tmp = tempfile.NamedTemporaryFile(
        mode="wb", suffix=".json", prefix="run_log_", delete=False
    )
    try:
        with open(log_path, "rb") as f:
            f.seek(start_pos)
            tmp.write(f.read())
    except OSError:
        pass
    finally:
        tmp.close()
    return Path(tmp.name)


def main(
    file_config: str,
    password_reader: Callable[[str], str] = _read_password,
    task_name: str | None = None,
) -> None:
    """Run backup tasks and send a status report email.

    When *task_name* is given only that task is executed; otherwise all
    tasks in the config are run in order.

    Args:
        file_config (str): Path to the YAML configuration file.
        password_reader: Callable that takes an env-var name and returns the
                         password string. Override in tests to avoid touching
                         the real filesystem or nix-sops secrets.
        task_name (str | None): If set, run only the task with this name.
    """
    setup_logging()

    gmail_password = password_reader("GMAIL_PASSWORD_FILE")

    # Record the current end of the log file so we can later extract only the
    # entries written during this run.
    app_log_path = Path("log.json").resolve()
    log_start_pos = app_log_path.stat().st_size if app_log_path.exists() else 0

    config = ConfigFile(file_config=file_config)
    backup = config.read()
    cfg = get_config()

    # Filter to the requested task when a name is supplied.
    tasks_to_run = backup["tasks"]
    if task_name is not None:
        tasks_to_run = [t for t in tasks_to_run if t["name"] == task_name]
        if not tasks_to_run:
            logger.error("No task named %r found in config — aborting", task_name)
            return

    run_log_path: Path | None = None
    with LogDB(cfg.DB_PATH) as log_db:
        lst_task_status = []
        for task_config in tasks_to_run:
            task_work_dir = Path(backup["dir_backup_local"].rstrip("/")) / task_config["name"]
            task_work_dir.mkdir(parents=True, exist_ok=True)
            task = BackupTask(
                task=task_config,
                dir_local=backup["dir_backup_local"],
                dir_remote=backup["dir_backup_remote"],
                work_dir=task_work_dir,
                ssh_config_file=cfg.SSH_CONFIG_PATH,
            )
            status = task.start()
            log_db.add_task_run(status)
            lst_task_status.append(status)

        run_log_path = _capture_run_log(app_log_path, log_start_pos)
        email = EmailReport(
            email_sender=backup["email_sender"],
            email_password=gmail_password,
            email_recipient=backup["email_report"],
            email_admin=backup["email_admin"],
            db_log=log_db,
            app_log=run_log_path,
        )
        email.send_mail(lst_task_status=lst_task_status)

    delete_logs(lst_task_status=lst_task_status)
    if run_log_path and run_log_path.exists():
        run_log_path.unlink()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("file_config", help="Path to the configuration file")
    parser.add_argument("--task", default=None, help="Run only the named task")
    args = parser.parse_args()
    main(file_config=args.file_config, task_name=args.task)
