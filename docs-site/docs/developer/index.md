---
icon: lucide/code-2
---

# Developer guide

This guide is for contributors and anyone who wants to understand, extend, or deploy Mnemosynce from source. It assumes familiarity with Python, Flask, and basic shell scripting.

## Repository layout

```
mnemosynce/
├── src/
│   ├── backup_server/          # Core backup engine (no Flask dependency)
│   │   ├── backup_task.py      # Orchestrates one task: backup → retention → sync
│   │   ├── config_file.py      # Reads and validates backup_config.yml
│   │   ├── database.py         # SQLite writer (LogDB)
│   │   ├── email_report.py     # Composes and sends the HTML status email
│   │   ├── logging_config.py   # JSON structured logging setup
│   │   ├── main.py             # CLI entry point
│   │   ├── backup.sh           # rsync snapshot script
│   │   ├── delete_old_backups.sh     # Retention policy script
│   │   ├── sync_backup_to_remote.sh  # Remote sync script
│   │   └── templates/          # Jinja2 email templates
│   ├── config/
│   │   └── config.py           # Flask config classes (Dev / Test / Production)
│   └── web/
│       ├── app.py              # Flask application factory
│       ├── auth.py             # Login/logout + login_required decorator
│       ├── dashboard_data.py   # Read-only SQLite queries for the dashboard
│       ├── run_state.py        # Thread-safe live run progress (SSE source)
│       ├── scheduler.py        # APScheduler singleton + live log bridging
│       ├── setup_guard.py      # setup_complete_required decorator
│       ├── setup_state.py      # Session-backed readiness checks
│       ├── routes/             # Flask blueprints (one file per feature area)
│       │   ├── config_editor.py
│       │   ├── connections.py
│       │   ├── dashboard.py
│       │   ├── main.py
│       │   ├── progress.py
│       │   ├── schedule.py
│       │   ├── setup_wizard.py
│       │   └── ssh_keys.py
│       ├── static/             # CSS and images
│       └── templates/web/      # Jinja2 page templates
├── backup.sh                   # rsync snapshot script
├── delete_old_backups.sh       # Retention policy script
├── sync_backup_to_remote.sh    # Remote sync script
├── tests/                      # pytest suite
├── docker/Dockerfile
├── pyproject.toml
└── docs-site/                  # This documentation
```

## Key design decisions

**Backup engine is Flask-free.** `src/backup_server/` has no Flask imports. It can be run directly from the CLI (`python -m backup_server.main config.yml`) or called from the web scheduler. This keeps the engine independently testable and deployable.

**Single SQLite database, two access paths.** `LogDB` (in `backup_server/database.py`) writes run results; `dashboard_data.py` (in `web/`) reads them with separate read-only queries. Both access the same `log.db` file but are never imported together.

**Live progress via SSE.** `RunState` in `run_state.py` is a module-level singleton shared between the scheduler thread (writer) and the Flask SSE endpoint (reader). A `threading.Lock` guards all mutations. The SSE stream in `progress.py` polls `RunState` at 300 ms intervals and pushes `line` and `state` events to the browser.

**Setup state is session-scoped.** The four readiness checks are re-derived from the filesystem on every request. Only the connection-test result is stored in the Flask session (because it can't be inferred from disk). This means no extra database tables and no migration concerns, at the cost of re-running the wizard after a server restart if setup wasn't complete.
