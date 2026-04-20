---
icon: lucide/archive-restore
---

# Restoring from a backup

Mnemosynce stores backups as **plain directories**. Each snapshot is a complete, browsable copy of your source at the time it was taken — no proprietary format, no special tool needed to read it. You restore with `rsync` or `cp`, the same tools that created the backup.

## Understanding the snapshot layout

Each task gets its own subdirectory under `dir_backup_local`, with one dated folder per snapshot:

```
/mnt/backup/local/
└── ServerData/               ← task name
    ├── 2026-04-14/           ← each date is a complete snapshot
    ├── 2026-04-15/
    ├── 2026-04-16/
    ├── 2026-04-17/
    ├── 2026-04-18/
    ├── 2026-04-19/
    └── 2026-04-20/           ← most recent
```

Snapshots appear complete because unchanged files are stored as **hard links** to the previous snapshot rather than copies. This means:

- You can browse any snapshot as a normal directory and see all files.
- Copying from a snapshot gives you real, independent files — the hard links are transparent.
- Deleting one snapshot does not affect files in any other snapshot.

---

## Choosing which snapshot to restore from

The [retention policy](configuration.md#retention-policy) keeps snapshots at daily, weekly, monthly, and yearly granularity. To find the right point in time, list the available snapshots:

```bash
ls /mnt/backup/local/ServerData/
```

```
2026-03-01   2026-03-31   2026-04-06   2026-04-13   2026-04-14
2026-04-15   2026-04-16   2026-04-17   2026-04-18   2026-04-19
2026-04-20
```

Pick the date that represents the state you want to restore to. The most recent is always the rightmost when sorted alphabetically.

---

## Restoring files

### Restore a single file or directory

Navigate directly into the snapshot and copy what you need:

```bash
cp /mnt/backup/local/ServerData/2026-04-19/home/user/documents/report.pdf \
   /home/user/documents/report.pdf
```

Or copy an entire subdirectory:

```bash
cp -a /mnt/backup/local/ServerData/2026-04-19/home/user/projects/ \
      /home/user/projects-restored/
```

The `-a` flag preserves permissions, timestamps, and ownership.

### Restore an entire task to its original location

Use `rsync` to push the snapshot back to the source — this is the mirror image of the original backup command:

```bash
rsync -az --delete \
  /mnt/backup/local/ServerData/2026-04-19/ \
  /data/
```

!!! warning "--delete will remove files added after the snapshot date"
    The `--delete` flag makes the destination exactly match the snapshot, including removing anything that did not exist on that date. Omit it if you only want to add or update files without removing anything.

### Restore to a remote source machine

If the original source was a remote machine (`user@desktop:/home/user`), restore over SSH the same way:

```bash
rsync -az /mnt/backup/local/DesktopHome/2026-04-19/ \
      user@desktop:/home/user/
```

---

## Restoring from the remote store

If the local backup drive is lost or damaged, restore from the remote store (`dir_backup_remote`) instead. The remote location has the same directory structure:

```bash
rsync -az \
  -e "ssh -i /root/.ssh/id_ed25519_backup" \
  user@backup-host:/mnt/backup/remote/ServerData/2026-04-19/ \
  /data/
```

The `-e` flag specifies the same key that Mnemosynce uses for its sync step.

---

## Browsing a snapshot inside Docker

If Mnemosynce runs in Docker and your backup volume is mounted at `/mnt/backup`, you can browse a snapshot from outside the container without stopping it:

```bash
ls /mnt/backup/local/ServerData/2026-04-19/
```

The volume is a normal filesystem directory — no need to exec into the container.

---

## What is not in the backup

Files matched by the `excludes` patterns in your `backup_config.yml` were never copied and cannot be restored. Check your configuration if an expected file is missing from a snapshot.
