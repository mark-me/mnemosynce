---
icon: lucide/activity
---

# Monitoring

Mnemosynce gives you two live views and a full history log to keep tabs on your backups.

## Dashboard

**Navigation → Dashboard**

The dashboard is the default home after setup. It shows:

- **Summary cards** — total runs, successful runs, failed runs, time of last run
- **Per-task table** — run counts, success rate progress bar, last run timestamp
- **Recent runs** — the five most recent task runs with step-level badges (bak / ret / syn)

### Readiness strip

When any of the four setup checks are still incomplete (config, SSH key, connection tested, schedule), a warning strip appears at the top of the dashboard with badge indicators and a direct link back to the relevant setup step.

### Full history

Click **Full history** (top right of the dashboard) or the clock icon next to any task to see a paginated, filterable log of every run. Expand any row to see step-by-step timing and source/destination paths.

---

## Progress view

**Navigation → Progress**

The progress view shows a **live terminal feed** of the current or most recent backup run using Server-Sent Events (SSE). The page updates automatically without any polling delay.

### Status indicators

| Badge | Meaning |
|-------|---------|
| :material-circle: `Running` (pulsing blue) | A backup is in progress |
| :material-check-circle: `Completed` (green) | Last run finished successfully |
| :material-close-circle: `Failed` (red) | Last run encountered an error |
| :material-circle-outline: `No run yet` (grey) | No backup has been run |

Step badges (**backup**, **retention**, **sync**) show the state of each individual step in the same colour scheme.

### Log output

The terminal panel streams log lines colour-coded by level:

| Colour | Level |
|--------|-------|
| White | Info |
| Yellow | Warning |
| Red | Error |
| Grey | Debug |

Use the autoscroll toggle (↓) to pause scrolling when inspecting earlier output. Click the trash icon to clear the display (does not delete the underlying logs).

---

## Email reports

After every scheduled or manual run, Mnemosynce sends an HTML email to `email_report` summarising:

- Which tasks ran and whether they succeeded
- Elapsed time per task and per step
- Days since last successful run per task
- Attached log files for any failed steps

If `email_admin` is set to a different address from `email_report`, that address is CC'd on failure-only emails.
