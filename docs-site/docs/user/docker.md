---
icon: lucide/container
---

# Docker deployment

This page covers production Docker deployment in more detail than the [installation guide](installation.md).

## Image

The official image is built from `docker/Dockerfile` and published to the GitHub Container Registry:

```
ghcr.io/mark-me/mnemosynce:latest
```

The image is based on `ghcr.io/astral-sh/uv:python3.13-alpine` and includes:

- Python 3.13 (via uv)
- `rsync` — used by `backup.sh` and `sync_backup_to_remote.sh`
- `openssh-client` — `ssh`, `ssh-keygen`, `ssh-keyscan` for key management and remote checks
- `sshpass` — used by the Connections page to install public keys on remote hosts
- `bash` — the shell scripts require bash, not sh

## Volume mount

The single volume `/data` holds all persistent state:

```
/data/
├── backup_config.yml   ← your backup configuration
├── log.db              ← SQLite run history
├── schedule.json       ← saved cron schedule
└── ssh/                ← generated SSH keypairs and known_hosts
    ├── ssh_config      ← auto-generated SSH client config
    ├── known_hosts     ← trusted remote host keys
    └── <keyname>       ← private keys (mode 600)
```

Mount your own directory here:

```yaml
volumes:
  - /data/mnemosynce:/data
```

!!! warning "Do not lose this directory"
    All configuration, run history, SSH keys, and trusted host keys live here. Back it up, or at minimum keep your `backup_config.yml` in version control.

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

## Standard docker-compose.yml

A minimal production setup exposing the web UI directly on port 5003:

```yaml
services:
  mnemosynce:
    image: ghcr.io/mark-me/mnemosynce:latest
    container_name: mnemosynce
    restart: unless-stopped
    ports:
      - "5003:5000"
    volumes:
      - /data/mnemosynce:/data
      - /mnt/backup:/mnt/backup
    env_file:
      - .env
    environment:
      - APP_ENV=production
      - TZ=Europe/Amsterdam
```

Store secrets in `.env` alongside the compose file:

```ini title=".env"
SECRET_KEY=a-long-random-string
ADMIN_USER=admin
ADMIN_PASSWORD=change-me
GMAIL_ADDRESS=your.account@gmail.com
GMAIL_PASSWORD=your-16-char-app-password
```

## Tailscale

If your remote backup sources or destinations are only reachable via [Tailscale](https://tailscale.com), the container must be able to route to Tailscale IP addresses (`100.x.x.x`). The simplest approach depends on whether the Docker host is itself a Tailscale node.

### Host is a Tailscale node (recommended)

When the machine running Docker is already enrolled in your Tailscale network, use `network_mode: host` so the container shares the host's network namespace and inherits its Tailscale routes:

```yaml
services:
  mnemosynce:
    image: ghcr.io/mark-me/mnemosynce:latest
    container_name: mnemosynce
    restart: unless-stopped
    network_mode: host          # shares host network — Tailscale IPs reachable
    volumes:
      - /data/mnemosynce:/data
      - /mnt/backup:/mnt/backup
    env_file:
      - .env
    environment:
      - APP_ENV=production
      - TZ=Europe/Amsterdam
```

!!! note "Ports with network_mode: host"
    With `network_mode: host` the container binds directly to the host's port 5000. Remove any `ports:` mapping — it is ignored and unnecessary. Make sure nothing else on the host uses port 5000.

!!! note "TSDProxy with network_mode: host"
    If you expose Mnemosynce via [TSDProxy](https://github.com/almeidapaulopt/tsdproxy), set `tsdproxy.hostname` to the host's LAN IP so TSDProxy can reach the app. The `tsdproxy.container_port` label still works:

    ```yaml
    labels:
      tsdproxy.enable: "true"
      tsdproxy.name: "mnemosynce"
      tsdproxy.container_port: "5000"
      tsdproxy.hostname: "192.168.2.19"
      tsdproxy.scheme: "http"
      tsdproxy.autodetect: "false"
    ```

### Host is not a Tailscale node

Run a Tailscale sidecar container and share its network namespace:

```yaml
services:
  tailscale:
    image: tailscale/tailscale:latest
    container_name: tailscale
    environment:
      - TS_AUTHKEY=tskey-auth-xxxx
      - TS_STATE_DIR=/var/lib/tailscale
    volumes:
      - /var/lib/tailscale:/var/lib/tailscale
      - /dev/net/tun:/dev/net/tun
    cap_add:
      - NET_ADMIN
      - SYS_MODULE
    restart: unless-stopped
    extra_hosts:
      - "pibackup:100.120.209.59"
      - "desktop-ubuntu:100.82.72.45"
    ports:
      - "5003:5000"

  mnemosynce:
    image: ghcr.io/mark-me/mnemosynce:latest
    container_name: mnemosynce
    restart: unless-stopped
    network_mode: "service:tailscale"   # share Tailscale's network namespace
    depends_on:
      - tailscale
    volumes:
      - /data/mnemosynce:/data
      - /mnt/backup:/mnt/backup
    env_file:
      - .env
    environment:
      - APP_ENV=production
      - TZ=Europe/Amsterdam
```

Move `ports:` and `extra_hosts:` to the `tailscale` service since it owns the network namespace.

### Trusting remote host keys over Tailscale

Regardless of which Tailscale approach you use, SSH connections to remote hosts require their host keys to be in `known_hosts` before a backup can sync. Do this once per host from the **Settings → Connections** page using the **Trust host key** panel — enter the hostname and click the button. The key is written to `/data/ssh/known_hosts` inside the persistent volume and survives container restarts.

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

## Updating

```bash
docker compose pull
docker compose up -d
```

The `/data` volume is preserved across image updates.
