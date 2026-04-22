import argparse
import logging
import os
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


def main(
    file_config: str,
    password_reader: Callable[[str], str] = _read_password,
) -> None:
    """Run all backup tasks and send a status report email.

    Args:
        file_config (str): Path to the YAML configuration file.
        password_reader: Callable that takes an env-var name and returns the
                         password string. Override in tests to avoid touching
                         the real filesystem or nix-sops secrets.
    """
    setup_logging()

    gmail_password = password_reader("GMAIL_PASSWORD_FILE")

    config = ConfigFile(file_config=file_config)
    backup = config.read()
    cfg = get_config()

    with LogDB(cfg.DB_PATH) as log_db:
        lst_task_status = []
        for task_config in backup["tasks"]:
            task = BackupTask(
                task=task_config,
                dir_local=backup["dir_backup_local"],
                dir_remote=backup["dir_backup_remote"],
            )
            status = task.start()
            log_db.add_task_run(status)
            lst_task_status.append(status)

        email = EmailReport(
            email_sender=backup["email_sender"],
            email_password=gmail_password,
            email_recipient=backup["email_report"],
            email_admin=backup["email_admin"],
            db_log=log_db,
        )
        email.send_mail(lst_task_status=lst_task_status)

    delete_logs(lst_task_status=lst_task_status)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("file_config", help="Path to the configuration file")
    args = parser.parse_args()
    main(file_config=args.file_config)
