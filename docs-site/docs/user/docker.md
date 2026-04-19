---
icon: lucide/container
---

# Docker deployment

This page covers production Docker deployment in more detail than the [installation guide](installation.md).

## Image

The official image is built from `docker/Dockerfile` and published to the GitHub Container Registry:

```
ghcr.io/mark-me/backup-server:latest
```

The image is based on `ghcr.io/astral-sh/uv:python3.13-alpine` and includes:

- Python 3.13 (via uv)
- `rsync` — used by `backup.sh` and `sync_backup_to_remote.sh`
- `openssh-client` — `ssh`, `ssh-keygen` for key management and remote checks
- `bash` — the shell scripts require bash, not sh

## Volume mount

The single volume `/data` holds all persistent state:

```
/data/
├── backup_config.yml   ← your backup configuration
├── log.db              ← SQLite run history
├── schedule.json       ← saved cron schedule
└── ssh/                ← generated SSH keypairs
```

Mount your own directory here:

```yaml
volumes:
  - ./mnemosynce-data:/data
```

!!! warning "Do not lose this directory"
    All configuration, run history, and SSH keys live here. Back it up, or at minimum keep your `backup_config.yml` in version control.

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | Yes (production) | Flask session secret — use a long random string |
| `ADMIN_USER` | No | Web UI username (default: `admin`) |
| `ADMIN_PASSWORD` | Yes (production) | Web UI password |
| `GMAIL_ADDRESS` | Yes | Gmail sender address |
| `GMAIL_PASSWORD` | Yes | Gmail [app password](https://support.google.com/accounts/answer/185833) |
| `DATA_ROOT` | No | Override the data directory (default: `/data`) |
| `APP_ENV` | No | `production` (default in Docker) or `development` |

## Reverse proxy (nginx)

To expose Mnemosynce over HTTPS behind nginx:

```nginx
server {
    listen 443 ssl;
    server_name backup.example.com;

    ssl_certificate     /etc/ssl/certs/backup.example.com.crt;
    ssl_certificate_key /etc/ssl/private/backup.example.com.key;

    location / {
        proxy_pass         http://localhost:5000;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;

        # Required for Server-Sent Events (live progress view)
        proxy_buffering    off;
        proxy_cache        off;
        proxy_read_timeout 3600s;
    }
}
```

!!! important "SSE and proxy buffering"
    The live progress view uses Server-Sent Events. If your proxy buffers responses, the terminal feed will appear frozen. Set `proxy_buffering off` and `proxy_read_timeout` to at least 60 seconds.

## GitHub Actions deployment

The scaffolded workflow at `.github/workflows/docs.yml` deploys the documentation site to GitHub Pages. For the application itself, add a step that pushes to your server via SSH or a container registry on each release.

## Updating

```bash
docker compose pull
docker compose up -d
```

The `/data` volume is preserved across image updates.
