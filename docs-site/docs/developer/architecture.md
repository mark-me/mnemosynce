---
icon: lucide/layers
---

# Architecture

## Component map

```mermaid
flowchart TD
    subgraph Browser
        UI[Web UI\nBootstrap 5 + SSE]
    end

    subgraph Flask["Flask application (src/web/)"]
        APP[app.py\nfactory]
        AUTH[auth.py]
        GUARD[setup_guard.py]
        STATE[setup_state.py]
        SCHED[scheduler.py\nAPScheduler]
        RS[run_state.py\nRunState singleton]
        ROUTES[Blueprint routes]
    end

    subgraph Engine["Backup engine (src/backup_server/)"]
        MAIN[main.py]
        TASK[backup_task.py]
        CFG[config_file.py]
        DB[database.py\nLogDB]
        EMAIL[email_report.py]
        SH["Shell scripts\nbackup.sh\ndelete_old_backups.sh\nsync_backup_to_remote.sh"]
    end

    subgraph Storage["Persistent storage (/data)"]
        YML[backup_config.yml]
        SQLITE[(log.db)]
        JSON[schedule.json]
        KEYS[ssh/]
    end

    UI -->|HTTP / SSE| ROUTES
    ROUTES --> AUTH
    ROUTES --> GUARD
    GUARD --> STATE
    STATE -->|reads| YML
    STATE -->|reads| JSON
    STATE -->|reads| KEYS
    STATE -->|session| Browser

    SCHED -->|calls| MAIN
    MAIN --> CFG --> YML
    MAIN --> TASK --> SH
    MAIN --> DB --> SQLITE
    MAIN --> EMAIL

    SCHED -->|pushes lines| RS
    RS -->|SSE stream| UI

    ROUTES -->|reads| SQLITE
```

## Request lifecycle

A typical page request goes through four layers:

1. **`@login_required`** — redirects to `/login` if the session has no `logged_in` flag (production only; bypassed in development).
2. **`@setup_complete_required`** — redirects to `/setup/` if `is_setup_complete()` returns False. Applied to all operational routes (dashboard, progress, schedule run/status).
3. **Route handler** — fetches data, renders template.
4. **Context processor** (`inject_setup_status`) — injects `setup_status` and `setup_complete` into every template so `base.html` can render the correct navbar without per-route logic.

## Threading model

The Flask development server and Gunicorn (with `--workers 2`) are both multi-threaded. Two threads can be active simultaneously:

| Thread | Writer | Reader |
|--------|--------|--------|
| Backup runner (APScheduler or manual) | `RunState.add_line()`, `RunState.step_*()` | — |
| Flask SSE handler (`/progress/stream`) | — | `RunState.lines_from()`, `RunState.snapshot()` |

`RunState` uses a `threading.Lock` on every mutation and read. The lock is held only for the duration of a list slice or attribute set — never across I/O — so contention is negligible.

## Data flow: a scheduled backup run

```mermaid
sequenceDiagram
    participant APSched as APScheduler
    participant Sched as scheduler.py
    participant RS as RunState
    participant Engine as backup_server.main
    participant DB as log.db
    participant SSE as /progress/stream
    participant Browser

    APSched->>Sched: trigger _run_backup(app)
    Sched->>RS: state.start(task_name)
    Sched->>Engine: main(config, password)
    loop per log record
        Engine-->>Sched: _StateHandler.emit(record)
        Sched->>RS: state.add_line(msg)
        Sched->>RS: state.step_running/done(...)
    end
    Engine->>DB: LogDB.add_task_run(status)
    Engine-->>Sched: return
    Sched->>RS: state.finish(success)

    loop SSE poll (300 ms)
        SSE->>RS: lines_from(seq)
        RS-->>SSE: new lines + seq
        SSE-->>Browser: event: line / state
    end
```
