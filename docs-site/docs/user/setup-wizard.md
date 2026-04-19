---
icon: lucide/wand
---

# First-time setup

When you open Mnemosynce for the first time — or whenever the setup checks are incomplete — you are guided through a four-step wizard before reaching the dashboard. You cannot skip to the monitoring views until setup is finished (or you click **Finish setup anyway**).

## The four steps

```mermaid
flowchart LR
    A[1 · Configuration] --> B[2 · SSH Keys]
    B --> C[3 · Connections]
    C --> D[4 · Schedule]
    D --> E([Dashboard])
    style E fill:#1D6A39,color:#fff,stroke:none
```

!!! info "Local-only sources skip steps 2 and 3"
    If every backup source in your configuration is a local path (no `user@host:` syntax), the SSH Keys and Connections steps are skipped automatically — you go straight from Configuration to Schedule.

---

### Step 1 — Configuration

Write your backup configuration in YAML. A template is pre-loaded to get you started. See the [Configuration reference](configuration.md) for every available field.

Click **Save configuration** to validate and persist the file. The **Next** button appears once the file is saved and valid.

---

### Step 2 — SSH Keys

Generate an ed25519 keypair for each remote host you need to access. After generating a key:

1. Copy the public key displayed on screen.
2. Paste it into `~/.ssh/authorized_keys` on the remote host.

You can generate as many keys as you need. The private keys never leave the server.

---

### Step 3 — Connections

Test that the server can reach its sources and send email.

| Test | What it checks |
|------|---------------|
| SSH | Ping → SSH login → (optionally) directory existence |
| Email | SMTP reachability → Gmail login → test message sent |

Run at least one successful test. The step is marked complete and the **Next** button activates. If you cannot get a test to pass, click **Skip for now** and fix it later from **Settings → Connections**.

---

### Step 4 — Schedule

Set a cron expression to run backups automatically. Use the quick-preset buttons or type your own expression.

| Preset | Expression | Runs |
|--------|-----------|------|
| Daily 02:00 | `0 2 * * *` | Every night at 02:00 UTC |
| Weekly Sun 03:00 | `0 3 * * 0` | Sunday nights at 03:00 UTC |
| Monthly 1st 04:00 | `0 4 1 * *` | First of each month at 04:00 UTC |
| Every 6 hours | `0 */6 * * *` | Four times a day |

Enable the **Enable automatic scheduling** checkbox and click **Save schedule**.

---

## Finishing setup

Setup completes via either path — whichever comes first:

- **Automatic** — all four checks pass (config saved, SSH key present, connection tested, schedule enabled). The wizard detects this and shows a *"Go to dashboard"* button.
- **Manual** — click **Finish setup anyway** on the Schedule step at any time. This sets a session flag that lets you through even if some checks are still pending.

!!! warning "Session-scoped state"
    The connection-test result is stored in your browser session. If the server restarts before setup is complete, you will return to the wizard and need to re-run the connection test. All other checks (config, SSH key, schedule) are re-derived from disk on every request.

---

## After setup

Once setup is complete, the navigation changes:

- **Before setup** — navbar shows the four wizard steps with amber indicators on incomplete ones.
- **After setup** — navbar shows Dashboard, Progress, Schedule, and a **Settings** dropdown (Configuration, SSH Keys, Connections).

The home route (`/`) redirects permanently to the Dashboard.
