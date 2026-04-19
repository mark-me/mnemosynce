---
icon: lucide/hard-drive-upload
---

# Backup engine

The backup engine (`src/backup_server/`) is a self-contained Python package with no Flask dependency. It can be invoked from the command line or called programmatically by the web scheduler.

## Entry point — `main.py`

```python
main(file_config="config.yml", password_reader=_read_password)
```

`main()` ties everything together:

1. Reads the Gmail password via `password_reader` (injectable for tests).
2. Opens a `LogDB` connection and runs each configured task in sequence.
3. Passes all task statuses to `EmailReport.send_mail()`.
4. Calls `delete_logs()` to remove per-step log files.

The `password_reader` parameter exists solely to make tests independent of the real filesystem and nix-sops secrets.

## `ConfigFile` — `config_file.py`

`ConfigFile(file_config).read()` loads and validates `backup_config.yml`. Validation checks:

- File exists.
- All required top-level keys are present (`dir_backup_local`, `dir_backup_remote`, `email_sender`, `email_report`, `tasks`).
- Each task has `name` and `dir_source`.
- `email_admin` is normalised to `""` when absent or equal to `email_report`.

Raises `FileNotFoundError` or `KeyError` on validation failure — the web config editor runs the same checks before saving and surfaces them as flash messages.

## `BackupTask` — `backup_task.py`

`BackupTask(task, dir_local, dir_remote).start()` runs the three-step workflow for a single task and returns a status dictionary.

### Step execution

Each step is run via `subprocess.run` (injectable via the `runner` parameter for tests). Steps run in order; if one fails the subsequent steps are skipped.

| Step | Script | Key rsync flags |
|------|--------|----------------|
| Backup | `backup.sh` | `-az --delete --hard-links --exclude-from=excludes.lst` |
| Retention | `delete_old_backups.sh` | Shell date arithmetic — no rsync |
| Sync | `sync_backup_to_remote.sh` | `-azhtH --numeric-ids --delete -e ssh -i /root/.ssh/id_ed25519_backup` |

### Error handling

`_stderr_has_error()` filters rsync stderr to distinguish real failures from known non-fatal warnings:

- `Permission denied (13)` — treated as a warning (rsync exit 23)
- `some files/attrs were not transferred` — treated as a warning
- Anything else in stderr with a non-zero exit code — fatal

### Status dictionary

`start()` returns a dict shaped like:

```python
{
    "name": "ServerData",
    "success": True,
    "dt_task_start": 1714000000.0,
    "dt_task_end":   1714000120.0,
    "steps": [
        {
            "step": "backup",
            "success": True,
            "dt_start": 1714000000.0,
            "dt_end":   1714000060.0,
            "time_elapsed": "00:01:00",
            "dir_from": "/data",
            "dir_to":   "/mnt/backup/local/ServerData/2026-04-19",
            "file_log": Path("ServerData_backup.log"),
        },
        # ... retention, sync
    ],
}
```

## `LogDB` — `database.py`

A thin SQLite wrapper using a single `task_run` table. Each row represents one step of one task run:

| Column | Type | Description |
|--------|------|-------------|
| `id_task` | TEXT | Task name |
| `dt_task_start` | REAL | Unix timestamp of task start |
| `dt_task_end` | REAL | Unix timestamp of task end |
| `success_task` | INTEGER | 1 if all steps succeeded |
| `id_step` | TEXT | `backup`, `retention`, or `sync` |
| `dt_step_start` | REAL | Step start timestamp |
| `dt_step_end` | REAL | Step end timestamp |
| `success_step` | INTEGER | 1 if this step succeeded |
| `dir_from` | TEXT | Source path |
| `dir_to` | TEXT | Destination path |
| `time_elapsed` | TEXT | `HH:MM:SS` string |

`LogDB` is used as a context manager (`with LogDB(...) as db:`). The web dashboard reads the same database via the separate `dashboard_data.py` module.

## `EmailReport` — `email_report.py`

`EmailReport.send_mail(lst_task_status)` enriches the raw status dicts, renders HTML and plain-text bodies via Jinja2, attaches any failed-step log files as zips, and sends via Gmail SMTP SSL on port 465.

`enrich_task_status()` is a pure function (separated from the class) that:

- Adds `time_task_elapsed`, formatted `dt_task_start`/`dt_task_end`.
- Looks up the last successful run per task from `LogDB` and sets `days_since_last_success`.
- Fills in any steps that were never reached (so templates always see all three steps).

## Shell scripts

The three bash scripts are baked into the Docker image and expected to exist in the working directory at runtime.

| Script | Arguments | Purpose |
|--------|-----------|---------|
| `backup.sh` | `NAME DIR_BACKUP DIR_SOURCE` | rsync snapshot with hard-link deduplication |
| `delete_old_backups.sh` | `NAME DIR_BACKUP` | Prune snapshots outside the retention window |
| `sync_backup_to_remote.sh` | `NAME DIR_LOCAL DIR_REMOTE` | rsync to remote storage over SSH |

!!! note
    The scripts write per-step log files (`<name>_backup.log`, etc.) to the current working directory. `main.py` deletes these after the email is sent.
