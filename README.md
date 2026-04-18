# backup-server

A Python-based backup orchestrator for Linux home servers. It runs a set of
rsync backup tasks defined in a YAML config file, applies a retention policy,
syncs to a remote location, and emails you a status report after every run.

## 🤔 How it works

Each run executes three steps per task, in order:

1. **Backup** — rsync from the source (local path or `user@host:/path`) to a
   dated snapshot directory on the local backup drive. Uses hard links to make
   each day's snapshot look complete while only storing changed files.
2. **Retention** — removes snapshots outside the configured retention window
   (daily for 7 days, weekly for 4 weeks, monthly for 12 months, yearly for 5 years).
3. **Sync** — rsync the local backup directory to a remote machine over SSH.

After all tasks finish, an HTML email report is sent summarising what succeeded
and what failed, with log files attached for any failed steps.

## 📝 Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- `rsync` installed on the backup server
- `rsync` and `ssh` access to any remote source machines (e.g. a desktop)
- An SSH key at `/root/.ssh/id_ed25519_backup` for syncing to the remote backup
- A Gmail account with an [app password](https://support.google.com/accounts/answer/185833)
  for sending the report email

## 📥 Installation

```bash
git clone https://github.com/mark-me/backup-server.git
cd backup-server
uv sync
```

## ⚙️ Configuration

Copy the example config and edit it:

```bash
cp config_example.yml config.yml
```

```yaml
# config.yml

# Local directory where backups are stored
dir_backup_local: /mnt/backup/local

# Remote destination (user@host:/path or a local path)
dir_backup_remote: user@backup-host:/mnt/backup/remote

# Email settings
email_sender: your.account@gmail.com
email_report: you@example.com
email_admin: admin@example.com  # CC'd on failure; remove or set equal to
                                # email_report to disable

tasks:
  - name: ServerData
    dir_source: /data          # Local path on this machine
    excludes:
      - downloads
      - tmp

  - name: DesktopHome
    dir_source: user@desktop:/home/user   # Remote source over SSH
    excludes:
      - Downloads/*
      - .cache
      - .Trash
```

### 📧 Email password

The Gmail app password is read from a file pointed to by the
`GMAIL_PASSWORD_FILE` environment variable. Never put the password directly in
the config or environment:

```bash
echo "your-app-password" > /etc/backup-server/gmail-password
chmod 600 /etc/backup-server/gmail-password
export GMAIL_PASSWORD_FILE=/etc/backup-server/gmail-password
```

If you use [nix-sops](https://github.com/Mic92/sops-nix) or a similar secrets
manager, point `GMAIL_PASSWORD_FILE` at the decrypted secret file it provides.

### 🔑 SSH keys

The sync step connects to the remote backup host using the key at
`/root/.ssh/id_ed25519_backup`. Set this up once with:

```bash
ssh-keygen -t ed25519 -f /root/.ssh/id_ed25519_backup
ssh-copy-id -i /root/.ssh/id_ed25519_backup.pub user@backup-host
```

Source machines (e.g. a desktop being backed up over SSH) need the server's
default key (`~/.ssh/id_rsa` or `~/.ssh/id_ed25519`) in their
`~/.ssh/authorized_keys`.

## 🚀 Running

```bash
uv run python -m backup_server.main config.yml
```

To run automatically, add a cron job or systemd timer. Example cron entry for
02:00 every night:

```
0 2 * * * cd /opt/backup-server && GMAIL_PASSWORD_FILE=/etc/backup-server/gmail-password uv run python -m backup_server.main /etc/backup-server/config.yml
```

## 🛠️ Development

Install dev dependencies:

```bash
uv sync --extra dev
```

Run the test suite:

```bash
uv run pytest -v
```

Run with coverage:

```bash
uv run pytest --cov=backup_server --cov-report=term-missing
```

The unit tests use no real subprocess calls, no real SMTP, and no real
filesystem outside of `tmp_path`. Tests marked `functional` run the actual
shell scripts and are excluded from CI:

```bash
uv run pytest -m "not functional"   # fast, no real scripts needed
uv run pytest -m functional         # requires the project to be fully set up
```

## 🧩 Project structure

```
backup-server/
├── src/backup_server/
│   ├── backup_task.py      # Runs backup, retention, and sync steps
│   ├── config_file.py      # Reads and validates the YAML config
│   ├── database.py         # SQLite log of every run (used for last-success dates)
│   ├── email_report.py     # Composes and sends the HTML status email
│   ├── logging_config.py   # JSON logging setup
│   ├── main.py             # Entry point — wires everything together
│   └── templates/          # Jinja2 templates for the email body
├── backup.sh               # rsync snapshot backup
├── delete_old_backups.sh   # Retention policy
├── sync_backup_to_remote.sh# Remote sync
├── tests/
└── config_example.yml
```

## ⚖️ License

MIT
