---
icon: lucide/key
---

# SSH keys

Mnemosynce uses SSH keys for two distinct purposes. Understanding which key does what will save you time when setting things up.

## Two key roles

| Key | Used for | Where it lives |
|-----|----------|---------------|
| **Source key** | Pulling data from remote source machines (e.g. your desktop) | Generated in the web UI, stored in `/data/ssh/` |
| **Remote sync key** | Pushing the local backup to the remote storage host | Hardcoded path: `/root/.ssh/id_ed25519_backup` |

---

## Source keys — managed in the web UI

Go to **Settings → SSH Keys** (or the **SSH Keys** step of the setup wizard).

### Generating a key

1. Enter a name — letters, numbers, hyphens, and underscores only (e.g. `desktop_mark`).
2. Optionally add a comment (e.g. `backup-server/desktop_mark`).
3. Click **Generate**.

The private key is saved to `/data/ssh/<name>` with mode `600`. The public key is shown immediately.

### Copying the public key to a remote host

After generating, copy the public key string displayed on screen and paste it into `~/.ssh/authorized_keys` on the remote machine:

```bash
# On the remote machine (e.g. your desktop)
echo "ssh-ed25519 AAAA...rest-of-key..." >> ~/.ssh/authorized_keys
```

Or use `ssh-copy-id` from the backup server if you still have password access:

```bash
ssh-copy-id -i /data/ssh/desktop_mark.pub user@desktop
```

### Testing the key

After copying the public key, go to **Settings → Connections** and run an SSH test with the same `user@host` pair. A successful test confirms the key is trusted.

---

## Remote sync key — manual setup

The `sync_backup_to_remote.sh` script always uses the key at `/root/.ssh/id_ed25519_backup`. Generate it once on the backup server:

```bash
ssh-keygen -t ed25519 -f /root/.ssh/id_ed25519_backup -N ""
ssh-copy-id -i /root/.ssh/id_ed25519_backup.pub user@backup-host
```

This key is **not** managed by the web UI and is not stored in `/data/ssh/`. However, the application detects it automatically at startup and includes it in the generated `/data/ssh/ssh_config`, so the sync script honours it alongside any UI-managed keys.

## Trusting remote host keys

Before an SSH connection can succeed non-interactively (during a backup run or a connection test), the remote host's public key must be present in `known_hosts`. Use the **Trust host key** panel on **Settings → Connections**:

1. Enter the hostname (e.g. `pibackup` or `desktop-ubuntu`).
2. Click **Trust host key**.

The application runs `ssh-keyscan` against that host and appends the result to `/data/ssh/known_hosts`. This file is inside the persistent data volume so it survives container restarts.

!!! tip "Do this before testing connections"
    Run **Trust host key** for every remote host before using the SSH connection test or triggering a backup run. SSH will refuse to connect to any host not in `known_hosts` when running non-interactively.

---

## Deleting a key

On the **SSH Keys** page, click **Delete** next to any key. Both the private and public key files are removed. If a backup task references that key's host, the backup step will fail until a new key is generated and installed.

!!! warning
    Deleting a key is irreversible. If you delete a key that is in active use, the corresponding backup task will fail at its next run.
