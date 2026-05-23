---
icon: lucide/file-code
---

# Configuration

Mnemosynce is configured through a single YAML file (`backup_config.yml`) edited directly in the web UI or with any text editor.

## Minimal example

```yaml
dir_backup_local:  /mnt/backup/local
dir_backup_remote: user@backup-host:/mnt/backup/remote
email_sender:      your.account@gmail.com
email_report:      you@example.com

tasks:
  - name: ServerData
    dir_source: /data
```

## Full example

```yaml
# Where backups are staged locally
dir_backup_local: /mnt/backup/local

# Where the local backup is synced for offsite storage
# Can be user@host:/path (SSH) or a local path
dir_backup_remote: user@backup-host:/mnt/backup/remote

# Gmail address used as the SMTP sender
email_sender: your.account@gmail.com

# Who receives the status report
email_report: you@example.com

# CC'd only when a task fails. Omit or set equal to email_report to disable.
email_admin: admin@example.com

# Global default schedule (optional).
# Applied to all tasks that don't have their own schedule override.
# Cron expression is evaluated in UTC.
schedule:
  cron: "0 4 * * *"   # every day at 04:00 UTC
  enabled: true

tasks:
  - name: ServerData
    dir_source: /data          # local path on this machine
    excludes:
      - downloads
      - tmp
      - "*.log"
    # No schedule key — inherits the global 04:00 schedule

  - name: DesktopHome
    dir_source: user@desktop:/home/user   # remote source over SSH
    excludes:
      - Downloads/*
      - .cache
      - .Trash
      - ".DS_Store"
    # Per-task override — runs at 22:00 instead of the global 04:00
    schedule:
      cron: "0 22 * * *"
      enabled: true
```

## Top-level fields

| Field | Required | Description |
|-------|----------|-------------|
| `dir_backup_local` | Yes | Local directory where task snapshots are stored |
| `dir_backup_remote` | Yes | Remote destination for the final sync step. Use `user@host:/path` for SSH or an absolute path for a locally-mounted drive |
| `email_sender` | Yes | Gmail address used as the From address and SMTP username |
| `email_report` | Yes | Address that receives the status report after every run |
| `email_admin` | No | Additional CC address for failure-only notifications. Omit or leave equal to `email_report` to disable |
| `schedule` | No | Global default schedule applied to all tasks (see below) |
| `tasks` | Yes | List of one or more task definitions (see below) |

## Schedule

The `schedule` section is optional and is managed by the web UI Schedule page, but you can also edit it directly in the YAML file. There are two levels:

**Global schedule** — a top-level `schedule` key that applies to every task with no per-task override.

**Per-task override** — a `schedule` key inside an individual task that overrides the global schedule for that task only.

| Field | Required | Description |
|-------|----------|-------------|
| `cron` | Yes | Standard five-field cron expression evaluated in UTC (e.g. `"0 4 * * *"` for daily at 04:00) |
| `enabled` | Yes | `true` to activate the schedule, `false` to save it without running |

Setting `enabled: false` preserves the cron expression while suspending automatic runs. A task with no `schedule` key inherits the global schedule. A task with `schedule.enabled: false` is excluded from automatic runs even if the global schedule is enabled.

See [Scheduling](scheduling.md) for the full guide including the web UI walkthrough.

## Task fields

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Unique label used in reports and dashboard |
| `dir_source` | Yes | Source to back up. Local absolute path or `user@host:/path` for remote |
| `excludes` | No | List of rsync-style glob patterns to exclude from the backup |

## Source path formats

=== "Local"

    ```yaml
    dir_source: /home/user
    ```

    Backs up a directory on the same machine running Mnemosynce.

=== "Remote (SSH)"

    ```yaml
    dir_source: user@hostname:/home/user
    ```

    Backs up from a remote machine over SSH. The backup server's SSH key must be in `~/.ssh/authorized_keys` on the remote host. See [SSH keys](ssh-keys.md).

## Retention policy

Mnemosynce applies a fixed retention window — you cannot currently change it per-task. Snapshots older than any of these windows are deleted after each run:

| Granularity | Kept for |
|-------------|---------|
| Daily | 7 days |
| Weekly | 4 weeks |
| Monthly | 12 months |
| Yearly | 5 years |

## Email password

The Gmail app password is never stored in the config file. Supply it through the environment:

=== "Docker"

    ```yaml title="docker-compose.yml"
    environment:
      GMAIL_PASSWORD: "your-16-char-app-password"
    ```

=== "Local / systemd"

    ```bash
    echo "your-app-password" > /etc/mnemosynce/gmail-password
    chmod 600 /etc/mnemosynce/gmail-password
    export GMAIL_PASSWORD_FILE=/etc/mnemosynce/gmail-password
    ```

    [nix-sops](https://github.com/Mic92/sops-nix) users can point `GMAIL_PASSWORD_FILE` at the decrypted secret file.

!!! tip "Gmail app password setup"
    Gmail requires a dedicated app password for SMTP access — your regular Google
    password will not work. See [Gmail app password](gmail-app-password.md) for
    step-by-step instructions.
