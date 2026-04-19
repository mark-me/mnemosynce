---
icon: lucide/flask-conical
---

# Testing

Mnemosynce uses `pytest`. All tests live in `tests/` and run without a real backup server, real SSH connections, or real SMTP.

## Running the tests

```bash
# Fast — no real scripts or network
uv run pytest -v -m "not functional"

# With coverage
uv run pytest -v -m "not functional" --cov=src --cov-report=term-missing

# Functional tests — requires the project to be fully set up on a real machine
uv run pytest -v -m functional
```

The CI pipeline (`.github/workflows/test.yml`) runs `pytest -m "not functional"`.

---

## Test files

| File | Covers |
|------|--------|
| `test_backup_task.py` | `BackupTask` — excludes file, subprocess runner, step status, error handling |
| `test_config_file.py` | `ConfigFile` — valid config, missing keys, optional fields |
| `test_database.py` | `LogDB` — table creation, inserting runs, last-success query |
| `test_email_report.py` | `enrich_task_status`, `EmailReport._compose_mail`, SMTP send, attachments |
| `test_main.py` | `main()` end-to-end with fakes, log cleanup, password reader |
| `test_setup_wizard.py` | `setup_state`, `setup_guard`, wizard routes |
| `test_functional.py` | Shell scripts (marked `functional`, excluded from CI) |

---

## Fixtures — `conftest.py`

### `minimal_config`

Writes a valid `backup_config.yml` to `tmp_path` and returns its `Path`. Used by backup engine tests that need a real file on disk.

```python
@pytest.fixture()
def minimal_config(tmp_path):
    cfg = {"dir_backup_local": ..., "tasks": [...], ...}
    p = tmp_path / "config.yml"
    p.write_text(yaml.dump(cfg))
    return p
```

### `fake_runner`

Returns a factory for constructing `subprocess.CompletedProcess` objects with configurable `returncode`, `stdout`, and `stderr`. Injected into `BackupTask` via the `runner` parameter.

```python
@pytest.fixture()
def fake_runner():
    def make(returncode=0, stdout="", stderr=""):
        def runner(*args, **kwargs):
            return subprocess.CompletedProcess(args, returncode, stdout, stderr)
        return runner
    return make
```

### `app` and `client` (wizard tests)

The wizard test fixtures create a `TestConfig` with all paths pointing to `tmp_path`, construct the Flask app, and return both the app and a `test_client()`. This keeps every test fully isolated — no shared filesystem state.

```python
@pytest.fixture()
def app(tmp_path):
    cfg = TestConfig()
    cfg.DATA_ROOT   = tmp_path
    cfg.CONFIG_PATH = tmp_path / "backup_config.yml"
    cfg.DB_PATH     = tmp_path / "log.db"
    cfg.SSH_KEY_DIR = tmp_path / "ssh"
    cfg.SSH_KEY_DIR.mkdir()
    yield create_app(cfg)
```

---

## Testing patterns

### Injecting a fake subprocess runner

`BackupTask` accepts a `runner` parameter so tests never shell out:

```python
def test_start_full_success(fake_runner, tmp_path):
    task = BackupTask(
        task={"name": "T", "dir_source": "/src"},
        dir_local=str(tmp_path),
        dir_remote="user@host:/remote",
        work_dir=tmp_path,
        runner=fake_runner(returncode=0),
    )
    status = task.start()
    assert status["success"] is True
```

### Testing Flask routes with `test_client`

The wizard tests use `client.get()` and `client.post()` against a fully wired Flask app in `TestConfig` mode. Because `APP_ENV` is not `"development"` in `TestConfig`, `login_required` would normally enforce authentication — but `TestConfig` sets `TESTING = True`, which the `login_required` decorator does not check. Instead, the wizard tests rely on `APP_ENV=test` falling through the `development` bypass, so routes are accessible without a session.

!!! note
    Check `web/auth.py` if this behaviour changes — the bypass condition is `APP_ENV == "development"`. Tests that need authenticated routes should set `session["logged_in"] = True` via `client.session_transaction()`.

### Testing session-backed state

Use `app.test_request_context()` to get a real Flask request context with an active session:

```python
def test_mark_connection_tested(app):
    with app.test_request_context():
        from flask import session
        from web.setup_state import mark_connection_tested
        mark_connection_tested()
        assert session.get("setup_connection_tested") is True
```

### Asserting redirect destinations

The wizard tests check `response.headers["Location"]` rather than following redirects, which keeps assertions fast and explicit:

```python
def test_redirects_to_setup_when_incomplete(client):
    response = client.get("/dashboard/", follow_redirects=False)
    assert response.status_code == 302
    assert "/setup/" in response.headers["Location"]
```

---

## Coverage

Run with:

```bash
uv run pytest -m "not functional" \
  --cov=src \
  --cov-report=term-missing \
  --cov-report=html:htmlcov
```

Open `htmlcov/index.html` for a line-level breakdown. The two pre-existing failures in `test_main.py` (`test_main_runs_without_real_secrets`, `test_password_reader_called_with_correct_env_var`) are caused by a missing `pythonjsonlogger` install in the bare test environment — they pass when the full dependency set is available via `uv sync --extra dev`.
