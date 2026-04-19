---
icon: lucide/globe
---

# Web application

The Flask application lives in `src/web/`. It is created by `create_app()` in `app.py` using the application factory pattern.

## Application factory — `app.py`

`create_app(config=None)` registers all blueprints, attaches a context processor, and starts the scheduler.

### Context processor

`inject_setup_status()` runs on every request and injects two variables into every template:

| Variable | Type | Description |
|----------|------|-------------|
| `setup_status` | `dict` | Full output of `get_setup_status(app)` |
| `setup_complete` | `bool` | Convenience alias for `setup_status["complete"]` |

`base.html` uses `setup_complete` to choose between the wizard navbar and the operations navbar without any per-route logic.

## Authentication — `auth.py`

`login_required` is a decorator that:

- In **development** (`APP_ENV=development`) — passes through unconditionally.
- In **production** — redirects to `/login` if `session["logged_in"]` is falsy.

Login is a simple username/password check against `ADMIN_USER` and `ADMIN_PASSWORD` from the Flask config (set via environment variables).

## Blueprints

| Blueprint | Prefix | Gated by |
|-----------|--------|----------|
| `auth` | — | — |
| `setup` | `/setup` | `login_required` only |
| `main` | — | `login_required` |
| `config_editor` | `/config` | `login_required` |
| `connections` | `/connections` | `login_required` |
| `ssh_keys` | `/ssh-keys` | `login_required` |
| `schedule` | `/schedule` | `login_required` + `setup_complete_required` (index, run-now, status only) |
| `dashboard` | `/dashboard` | `login_required` + `setup_complete_required` |
| `progress` | `/progress` | `login_required` + `setup_complete_required` |

`schedule.save` and `schedule.remove` are intentionally **not** gated by `setup_complete_required` — the wizard's Schedule step calls them before setup is complete.

## Live progress — `run_state.py` and `progress.py`

`RunState` is a module-level singleton (`state = RunState()`) shared between:

- `scheduler.py` (writer) — calls `state.start()`, `state.add_line()`, `state.step_running()`, `state.step_done()`, `state.finish()`.
- `progress.py` (reader) — calls `state.snapshot()` and `state.lines_from(seq)`.

The SSE endpoint at `GET /progress/stream` generates an infinite stream that:

1. Sends an initial `state` event with the current snapshot.
2. Polls every 300 ms for new lines via `lines_from(seq)`.
3. Pushes `line` events for each new log line, and a `state` event after each batch.
4. Sends a final `state` + `done` event when the run finishes, then closes.
5. Reconnects automatically after a 3-second back-off on network error.

The browser client uses `EventSource` and handles `line`, `state`, and `done` event types.

## Scheduler — `scheduler.py`

`get_scheduler()` returns a lazily-initialised `BackgroundScheduler` (APScheduler) singleton configured for UTC. The scheduler is started once at application boot via `init_scheduler(app)`.

`_run_backup(app)` is the job function. It:

1. Calls `state.start()`.
2. Attaches `_StateHandler` to the `backup_server` logger to bridge log records into `RunState`.
3. Calls `backup_server.main.main()`.
4. Removes the handler and calls `state.finish()`.

`_StateHandler` matches known log phrases to infer step transitions:

| Phrase in log (case-insensitive) | Action |
|----------------------------------|--------|
| `start backup` | `state.step_running("backup")` |
| `step 'backup' succeeded` | `state.step_done("backup", success=True)` |
| `step 'backup' failed` | `state.step_done("backup", success=False)` |
| *(same for `retention` and `sync`)* | |

## Dashboard data — `dashboard_data.py`

Read-only queries against `log.db` returning plain dicts and lists. The routes stay thin — they call these functions and pass the results directly to `render_template`.

Key functions:

| Function | Returns |
|----------|---------|
| `get_summary(db_path)` | Total/success/failed run counts, last run timestamp, task name list |
| `get_task_stats(db_path)` | Per-task run counts, success rate, last run timestamp |
| `get_task_history(db_path, task_name, limit)` | Paginated list of runs with step details |
