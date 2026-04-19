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

tasks:
  - name: ServerData
    dir_source: /data          # local path on this machine
    excludes:
      - downloads
      - tmp
      - "*.log"

  - name: DesktopHome
    dir_source: user@desktop:/home/user   # remote source over SSH
    excludes:
      - Downloads/*
      - .cache
      - .Trash
      - ".DS_Store"
```

## Top-level fields

| Field | Required | Description |
|-------|----------|-------------|
| `dir_backup_local` | Yes | Local directory where task snapshots are stored |
| `dir_backup_remote` | Yes | Remote destination for the final sync step. Use `user@host:/path` for SSH or an absolute path for a locally-mounted drive |
| `email_sender` | Yes | Gmail address used as the From address and SMTP username |
| `email_report` | Yes | Address that receives the status report after every run |
| `email_admin` | No | Additional CC address for failure-only notifications. Omit or leave equal to `email_report` to disable |
| `tasks` | Yes | List of one or more task definitions (see below) |

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

!!! tip "Generating a Gmail app password"
    Go to your Google Account → Security → 2-Step Verification → App passwords. Generate one labelled "Mnemosynce". The password is a 16-character string with no spaces.
