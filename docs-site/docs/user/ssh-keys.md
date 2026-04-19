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

This key is **not** managed by the web UI and is not stored in `/data/ssh/`.

---

## Deleting a key

On the **SSH Keys** page, click **Delete** next to any key. Both the private and public key files are removed. If a backup task references that key's host, the backup step will fail until a new key is generated and installed.

!!! warning
    Deleting a key is irreversible. If you delete a key that is in active use, the corresponding backup task will fail at its next run.
