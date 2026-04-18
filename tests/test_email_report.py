"""Tests for email_report.py."""
import time
from pathlib import Path

import pytest

from backup_server.database import LogDB
from backup_server.email_report import EmailReport, enrich_task_status
from tests.conftest import make_task_status, make_step


def make_report(db: LogDB, smtp_send=None, app_log=None) -> EmailReport:
    return EmailReport(
        email_sender="sender@example.com",
        email_password="secret",
        email_recipient="recipient@example.com",
        email_admin="admin@example.com",
        db_log=db,
        smtp_send=smtp_send or (lambda *a: None),
        app_log=app_log,
    )


# ---------------------------------------------------------------------------
# enrich_task_status (pure function — no faking needed)
# ---------------------------------------------------------------------------

def test_enrich_adds_elapsed_time(db):
    statuses = [make_task_status("photos", success=True)]
    enriched = enrich_task_status(statuses, db)
    assert "time_task_elapsed" in enriched[0]


def test_enrich_converts_timestamps_to_datetime(db):
    from datetime import datetime
    statuses = [make_task_status("photos", success=True)]
    enriched = enrich_task_status(statuses, db)
    assert isinstance(enriched[0]["dt_task_start"], datetime)
    assert isinstance(enriched[0]["dt_task_end"], datetime)


def test_enrich_fills_missing_steps(db):
    # Only the backup step ran
    statuses = [make_task_status("photos", success=False, steps=[make_step("backup", False)])]
    enriched = enrich_task_status(statuses, db)
    step_names = {s["step"] for s in enriched[0]["steps"]}
    assert step_names == {"backup", "retention", "sync"}


def test_enrich_does_not_duplicate_present_steps(db):
    statuses = [make_task_status("photos", success=True)]
    enriched = enrich_task_status(statuses, db)
    step_names = [s["step"] for s in enriched[0]["steps"]]
    assert len(step_names) == len(set(step_names))


def test_enrich_last_success_falls_back_to_task_end_when_no_history(db):
    statuses = [make_task_status("new-task", success=True)]
    enriched = enrich_task_status(statuses, db)
    assert enriched[0]["days_since_last_success"] == 0


def test_enrich_days_since_last_success_uses_db(db):
    # Store a run from 3 days ago
    old_status = make_task_status("photos", success=True)
    three_days = 3 * 24 * 3600
    old_status["dt_task_start"] -= three_days
    old_status["dt_task_end"] -= three_days
    for s in old_status["steps"]:
        s["dt_start"] -= three_days
        s["dt_end"] -= three_days
    db.add_task_run(old_status)

    current = make_task_status("photos", success=True)
    enriched = enrich_task_status([current], db)
    assert enriched[0]["days_since_last_success"] == pytest.approx(3, abs=1)


# ---------------------------------------------------------------------------
# _compose_mail
# ---------------------------------------------------------------------------

def test_compose_mail_subject_on_success(db, tmp_path):
    app_log = tmp_path / "log.json"
    app_log.write_text("{}")
    report = make_report(db, app_log=app_log)
    message = report._compose_mail([make_task_status("photos", success=True)])
    assert message["Subject"] == "Back-up succeeded"


def test_compose_mail_subject_on_failure(db, tmp_path):
    app_log = tmp_path / "log.json"
    app_log.write_text("{}")
    report = make_report(db, app_log=app_log)
    message = report._compose_mail([make_task_status("photos", success=False)])
    assert message["Subject"] == "Backup FAILED"


def test_compose_mail_cc_admin_on_failure(db, tmp_path):
    app_log = tmp_path / "log.json"
    app_log.write_text("{}")
    report = make_report(db, app_log=app_log)
    message = report._compose_mail([make_task_status("photos", success=False)])
    assert message["CC"] == "admin@example.com"


def test_compose_mail_no_cc_on_success(db, tmp_path):
    app_log = tmp_path / "log.json"
    app_log.write_text("{}")
    report = make_report(db, app_log=app_log)
    message = report._compose_mail([make_task_status("photos", success=True)])
    assert message["CC"] is None


def test_compose_mail_no_cc_when_admin_empty(db, tmp_path):
    app_log = tmp_path / "log.json"
    app_log.write_text("{}")
    report = EmailReport(
        email_sender="s@e.com",
        email_password="x",
        email_recipient="r@e.com",
        email_admin="",
        db_log=db,
        smtp_send=lambda *a: None,
        app_log=app_log,
    )
    message = report._compose_mail([make_task_status("photos", success=False)])
    assert message["CC"] is None


def test_compose_mail_has_html_and_plain_parts(db, tmp_path):
    app_log = tmp_path / "log.json"
    app_log.write_text("{}")
    report = make_report(db, app_log=app_log)
    message = report._compose_mail([make_task_status("photos", success=True)])
    content_types = [part.get_content_type() for part in message.get_payload()]
    assert "text/html" in content_types
    assert "text/plain" in content_types


# ---------------------------------------------------------------------------
# send_mail — captures outgoing calls via fake smtp_send
# ---------------------------------------------------------------------------

def test_send_mail_calls_smtp_send(db, tmp_path):
    app_log = tmp_path / "log.json"
    app_log.write_text("{}")
    sent = []
    def capture(sender, password, recipient, message_str):
        sent.append({"sender": sender, "recipient": recipient, "msg": message_str})

    report = make_report(db, smtp_send=capture, app_log=app_log)
    report.send_mail([make_task_status("photos", success=True)])
    assert len(sent) == 1
    assert sent[0]["sender"] == "sender@example.com"
    assert sent[0]["recipient"] == "recipient@example.com"


def test_send_mail_message_contains_subject(db, tmp_path):
    app_log = tmp_path / "log.json"
    app_log.write_text("{}")
    sent = []
    report = make_report(db, smtp_send=lambda s, p, r, m: sent.append(m), app_log=app_log)
    report.send_mail([make_task_status("photos", success=True)])
    assert "Back-up succeeded" in sent[0]


# ---------------------------------------------------------------------------
# _add_attachment
# ---------------------------------------------------------------------------

def test_add_attachment_zips_file(db, tmp_path):
    report = make_report(db)
    log_file = tmp_path / "test.log"
    log_file.write_text("log content")
    message = __import__("email.mime.multipart", fromlist=["MIMEMultipart"]).MIMEMultipart()
    report._add_attachment(message, log_file)
    zip_file = tmp_path / "test.zip"
    assert zip_file.exists()


def test_add_attachment_attaches_to_message(db, tmp_path):
    report = make_report(db)
    log_file = tmp_path / "test.log"
    log_file.write_text("log content")
    from email.mime.multipart import MIMEMultipart
    message = MIMEMultipart()
    report._add_attachment(message, log_file)
    # The message should now have one attachment
    attachments = [p for p in message.get_payload() if p.get_filename()]
    assert len(attachments) == 1
    assert attachments[0].get_filename() == "test.zip"
