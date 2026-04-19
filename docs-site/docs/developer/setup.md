---
icon: lucide/terminal
---

# Developer setup

## Prerequisites

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/) — fast Python package manager
- `rsync` and `openssh-client` on your PATH (for functional tests only)

## Clone and install

```bash
git clone https://github.com/mark-me/backup-server.git
cd backup-server
uv sync --extra dev
```

This installs the application dependencies plus the dev extras: `pytest`, `pytest-cov`, `mypy`, and `ruff`.

## Environment

```bash
cp .env.example .env
# Edit .env — the defaults work for development
```

```ini title=".env"
APP_ENV=development        # disables login checks
SECRET_KEY=change-me-locally
ADMIN_USER=admin
ADMIN_PASSWORD=dev-password
GMAIL_ADDRESS=your.account@gmail.com
GMAIL_PASSWORD=your-app-password
DATA_ROOT=dev-data         # created automatically
```

In `development` mode:

- All routes are accessible without logging in
- `DATA_ROOT` defaults to `dev-data/` in the project root
- Debug mode is on (auto-reload on code changes)

## Run the dev server

```bash
uv run flask --app src/web/app:create_app run --host 0.0.0.0 --port 5000
```

Or use the VS Code launch configuration in `.vscode/launch.json`.

## Code style

```bash
uv run ruff check src/ tests/      # lint
uv run ruff format src/ tests/     # format
uv run mypy src/                   # type check
```

Ruff is configured in `pyproject.toml` with `line-length = 100` and the `E`, `F`, `I`, `UP` rule sets.

## Project dependencies

Core runtime dependencies (from `pyproject.toml`):

| Package | Purpose |
|---------|---------|
| `flask` | Web framework |
| `gunicorn` | Production WSGI server |
| `APScheduler` | Cron-style background job scheduler |
| `PyYAML` | Parsing `backup_config.yml` |
| `jinja2` | Email and HTML templating |
| `python-dotenv` | Loading `.env` in development |
| `python-json-logger` | Structured JSON logging |
