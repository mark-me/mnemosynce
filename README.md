# Mnemosynce

**Remember everything.**

A beautiful, reliable backup orchestrator for Linux home servers. Mnemosynce (Mnemosyne + Sync) creates dated snapshots with `rsync`, enforces smart retention policies, syncs to remote storage, and keeps you informed via email — all managed through a clean web dashboard.

![Mnemosynce Logo Concept](docs/images/Modern Tech Logo of Mnemosyne wide.png)
*Ancient memory meets modern sync*

## ✨ Features

- **Snapshot Backups** — Efficient daily/weekly/monthly/yearly snapshots using `rsync` + hard links
- **Smart Retention** — Automatically prunes old backups according to your policy
- **Remote Sync** — Securely mirrors everything to a secondary location over SSH
- **Web Dashboard** — Real-time status, history, configuration editor, and progress monitoring
- **Scheduled Runs** — Built-in APScheduler with flexible cron-style timing
- **Email Reports** — Rich HTML summaries with log attachments on failures
- **Multi-Platform** — Supports local paths and remote SSH sources (`user@host:/path`)

## 🎨 Design

- **Colors**: Deep mythological blues & purples with vibrant teal accents
- **Vibe**: Calm, trustworthy, timeless — like an ancient library that never forgets

## 📥 Quick Start

### Docker (Recommended)

```bash
docker run -d \
  --name mnemosynce \
  -v ./data:/data \
  -p 5000:5000 \
  ghcr.io/mark-me/mnemosynce:latest
```

Then open [http://your-server:5000](http://your-server:5000)

### Manual Installation

```bash
git clone https://github.com/mark-me/mnemosynce.git
cd mnemosynce
uv sync
cp .env.example .env          # edit as needed
uv run python -m web.app      # or use gunicorn in production
```

## ⚙️ Configuration

All persistent data lives in the `/data` volume (or `dev-data/` in development):

- `backup_config.yml` - Define your backup tasks
- `log.db` - History for the dashboard
- SSH keys for remote operations
- Gmail credentials (via file for security)

Example backup_config.yml:

```yaml
dir_backup_local: /mnt/backup/local
dir_backup_remote: user@backup-host:/mnt/backup/remote

email_sender: you@gmail.com
email_report: you@example.com

tasks:
  - name: Documents
    dir_source: /home/user/Documents
    excludes:
      - "*.tmp"
      - "cache/"
```

## 🛠️ Development

```bash
uv sync --extra dev
uv run flask --app web.app run --debug
```

Run test:

```bash
uv run pytest -m "not functional"
```

### Project structure (key parts)

```text
mnemosynce/
├── src/backup_server/     # Core backup logic + shell scripts
├── src/web/               # Flask + dashboard + scheduler
├── backup.sh
├── delete_old_backups.sh
├── sync_backup_to_remote.sh
├── docker/Dockerfile
└── data/                  # ← mounted volume in production
```

### License

MIT © 2026 Mark Zwart

---

"Your data's eternal memory keeper."
