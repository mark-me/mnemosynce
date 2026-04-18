import logging
import smtplib
import ssl
import time
from collections.abc import Callable
from datetime import datetime
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from jinja2 import Environment, FileSystemLoader

from .database import LogDB

logger = logging.getLogger(__name__)

_EXPECTED_STEPS = ["backup", "retention", "sync"]


def enrich_task_status(lst_task_status: list, db_log: LogDB) -> list:
    """Add timing fields, last-success info, and fill in missing steps.

    This is a pure data-shaping step that does not belong inside EmailReport.

    Args:
        lst_task_status (list): Raw task status dicts from BackupTask.start().
        db_log (LogDB): Database used to look up last successful run timestamps.

    Returns:
        list: Enriched copies of the task status dicts.
    """
    dict_last_success = db_log.get_tasks_last_success()
    for status in lst_task_status:
        elapsed = status["dt_task_end"] - status["dt_task_start"]
        status["time_task_elapsed"] = time.strftime("%H:%M:%S", time.gmtime(elapsed))
        status["dt_task_end"] = datetime.fromtimestamp(status["dt_task_end"])
        status["dt_task_start"] = datetime.fromtimestamp(status["dt_task_start"])

        last_ts = dict_last_success.get(status["name"])
        status["dt_last_success"] = (
            datetime.fromtimestamp(last_ts) if last_ts else status["dt_task_end"]
        )
        status["days_since_last_success"] = (status["dt_task_end"] - status["dt_last_success"]).days

        # Fill in steps that were never reached so templates always see all three
        present = {step["step"] for step in status["steps"]}
        for step_name in _EXPECTED_STEPS:
            if step_name not in present:
                status["steps"].append({"step": step_name, "success": False, "time_elapsed": "N/A"})
    return lst_task_status


def _smtp_send(sender: str, password: str, recipient: str, message_str: str) -> None:
    """Send an email via Gmail SMTP SSL. The default smtp_send implementation."""
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(host="smtp.gmail.com", port=465, context=context) as smtp:
        smtp.login(sender, password=password)
        smtp.sendmail(from_addr=sender, to_addrs=recipient, msg=message_str)


class EmailReport:
    def __init__(
        self,
        email_sender: str,
        email_password: str,
        email_recipient: str,
        db_log: LogDB,
        email_admin: str = "",
        smtp_send: Callable[[str, str, str, str], None] = _smtp_send,
        app_log: Path = None,
    ) -> None:
        """
        Args:
            email_sender (str): The Gmail address to send from.
            email_password (str): The Gmail app password.
            email_recipient (str): Primary recipient of the report.
            db_log (LogDB): Shared database instance for last-success lookups.
            email_admin (str): CC'd on failure; leave empty to skip.
            smtp_send: Callable that delivers the message. Override in tests to
                       capture outgoing mail without hitting a real SMTP server.
                       Signature: (sender, password, recipient, message_str) -> None
            app_log (Path): Path to the application log file to attach. Defaults
                            to log.json in cwd. Override in tests to use a tmp file.
        """
        self._email_sender = email_sender
        self._email_password = email_password
        self._email_recipient = email_recipient
        self._email_admin = email_admin
        self._db_log = db_log
        self._smtp_send = smtp_send
        self._app_log = app_log or Path("log.json").resolve()
        template_dir = Path(__file__).parent / "templates"
        env = Environment(loader=FileSystemLoader(str(template_dir)))
        self._templates = {
            "html": env.get_template("status_template.html"),
            "plain": env.get_template("status_template.txt"),
        }

    def send_mail(self, lst_task_status: list) -> None:
        """Create and send an email reporting on the task execution.

        Args:
            lst_task_status (list): Dictionaries for each task execution.
        """
        message = self._compose_mail(lst_task_status)
        log_ctx = f"back-up report email to '{self._email_recipient}' from '{self._email_sender}'"
        try:
            self._smtp_send(
                self._email_sender,
                self._email_password,
                self._email_recipient,
                message.as_string(),
            )
            logger.info(f"Sent {log_ctx}")
        except smtplib.SMTPSenderRefused:
            logger.error(f"Could not send {log_ctx}")

    def _compose_mail(self, lst_task_status: list) -> MIMEMultipart:
        """Compose and return the MIME message.

        Args:
            lst_task_status (list): Dictionaries for each task execution.
        """
        lst_task_status = enrich_task_status(lst_task_status, self._db_log)
        backup_success = all(item["success"] for item in lst_task_status)

        message = MIMEMultipart("alternative")
        message["From"] = self._email_sender
        message["To"] = self._email_recipient
        if not backup_success and self._email_admin:
            message["CC"] = self._email_admin
        message["Subject"] = "Back-up succeeded" if backup_success else "Backup FAILED"

        for mime_subtype, template in self._templates.items():
            content = template.render(tasks=lst_task_status)
            message.attach(MIMEText(content, mime_subtype))

        self._add_attachment(message, self._app_log)
        for task in lst_task_status:
            for step in task["steps"]:
                if not step["success"] and "file_log" in step:
                    self._add_attachment(message, step["file_log"])

        return message

    def _add_attachment(self, message: MIMEMultipart, file: Path) -> None:
        """Zip a file and attach it to the message.

        Args:
            message (MIMEMultipart): The message to attach to.
            file (Path): The file to zip and attach.
        """
        file = file.resolve()
        file_zip = file.parent / f"{file.stem}.zip"
        if file_zip.exists():
            file_zip.unlink()
        with ZipFile(file_zip, mode="w", compression=ZIP_DEFLATED, compresslevel=9) as zf:
            zf.write(file, arcname=file.name)
        with open(file_zip, "rb") as fh:
            message.attach(MIMEApplication(fh.read(), Name=file_zip.name))
