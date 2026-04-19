---
icon: lucide/package
---

# Installation

Mnemosynce is distributed as a Python package and runs inside Docker in production. Pick the path that suits your setup.

## Option A — Docker (recommended for production)

Docker is the simplest way to run Mnemosynce on a home server. It bundles Python, `rsync`, `ssh`, and the web UI into a single image.

### Prerequisites

- Docker and Docker Compose installed on your backup server
- Port 5000 available (or change the mapping below)

### docker-compose.yml

Create a `docker-compose.yml` wherever you want to manage the service:

```yaml
services:
  mnemosynce:
    image: ghcr.io/mark-me/backup-server:latest
    restart: unless-stopped
    ports:
      - "5000:5000"
    volumes:
      - /mnt/backup:/mnt/backup       # your backup storage
      - ./data:/data                  # config, database, SSH keys
    environment:
      SECRET_KEY: "change-me-to-a-random-string"
      ADMIN_USER: "admin"
      ADMIN_PASSWORD: "change-me"
      GMAIL_ADDRESS: "your.account@gmail.com"
      GMAIL_PASSWORD: "your-16-char-app-password"
```

Start it:

```bash
docker compose up -d
```

Open `http://<your-server>:5000` in a browser. You will land on the [setup wizard](setup-wizard.md).

!!! warning "Change the defaults"
    The container refuses to start in production if `SECRET_KEY` or `ADMIN_PASSWORD` are left as the placeholder strings. Set them to strong, unique values before going live.

---

## Option B — Local Python install

Use this for development or if you prefer not to use Docker.

### Prerequisites

- Python 3.12 or newer
- [`uv`](https://docs.astral.sh/uv/) package manager
- `rsync` and `openssh-client` available on the system

```bash
# Install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Clone and install

```bash
git clone https://github.com/mark-me/backup-server.git
cd backup-server
uv sync
```

### Configure environment

Copy the example file and fill in your values:

```bash
cp .env.example .env
```

```ini title=".env"
APP_ENV=development        # use "production" on a real server
SECRET_KEY=change-me
ADMIN_USER=admin
ADMIN_PASSWORD=change-me
GMAIL_ADDRESS=your.account@gmail.com
GMAIL_PASSWORD=your-app-password
```

### Start the web server

```bash
uv run flask --app src/web/app:create_app run --host 0.0.0.0 --port 5000
```

For production use Gunicorn instead:

```bash
uv run gunicorn \
  --bind 0.0.0.0:5000 \
  --workers 2 \
  --timeout 120 \
  "web.app:create_app()"
```

---

## Data directory

Both install methods use a single persistent directory (`/data` in Docker, `dev-data/` locally) that holds:

| File | Purpose |
|------|---------|
| `backup_config.yml` | Your backup task definitions |
| `log.db` | SQLite database of every run |
| `schedule.json` | Saved cron schedule |
| `ssh/` | Generated SSH keypairs |

Mount or back up this directory — it is everything Mnemosynce needs to survive a restart.
