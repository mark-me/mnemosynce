---
icon: lucide/user
---

# User guide

This guide covers everything you need to get Mnemosynce running and keeping your data safe — from installation through day-to-day monitoring.

## What you will need

Before you begin, make sure you have:

- A Linux server that will run Mnemosynce (the *backup server*)
- One or more machines whose data you want to back up (can include the backup server itself)
- A destination for the remote copy — another machine reachable over SSH, or a locally-mounted drive
- A Gmail account with an [app password](https://support.google.com/accounts/answer/185833) for email reports

## Steps at a glance

- [x] [Install](installation.md) Mnemosynce on your backup server
- [ ] Complete the [first-time setup wizard](setup-wizard.md) in the web UI
- [ ] Write your [backup configuration](configuration.md)
- [ ] Generate [SSH keys](ssh-keys.md) for passwordless access to remote hosts
- [ ] Test connectivity and [set a schedule](scheduling.md)
- [ ] Watch your first run in the [dashboard and progress view](monitoring.md)
- [ ] Know how to [restore files](restoring.md) when you need them
