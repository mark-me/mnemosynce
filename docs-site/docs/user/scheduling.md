---
icon: lucide/clock
---

# Scheduling

Backups can run on a fixed schedule using a standard cron expression, or triggered manually from the web UI at any time.

## Setting a schedule

Go to **Schedule** in the navigation bar (or the Schedule step of the setup wizard).

Enter a five-field cron expression or pick a preset:

| Preset | Expression | Description |
|--------|-----------|-------------|
| Daily 02:00 | `0 2 * * *` | Every night at 02:00 UTC |
| Weekly Sun 03:00 | `0 3 * * 0` | Sunday nights |
| Monthly 1st 04:00 | `0 4 1 * *` | First day of each month |
| Every 6 hours | `0 */6 * * *` | Four runs per day |

Check **Enable automatic scheduling** and click **Save schedule**. The next run time is shown immediately.

!!! note "All times are UTC"
    The scheduler runs in UTC. If you are in a UTC+2 timezone and want a 02:00 local run, use `0 0 * * *`.

## Cron expression reference

```
┌───────── minute  (0–59)
│ ┌─────── hour    (0–23)
│ │ ┌───── day     (1–31)
│ │ │ ┌─── month   (1–12)
│ │ │ │ ┌─ weekday (0–6, Sun=0)
│ │ │ │ │
0 2 * * *
```

Special characters: `*` any, `,` list, `-` range, `/` step.

Use [crontab.guru](https://crontab.guru) to check an expression before saving.

## Triggering a manual run

Click **Run now** on either the Schedule page or the Progress page. The backup starts immediately in a background thread and you are redirected to the Progress view to watch it live.

!!! info
    A manual run does not interfere with the cron schedule. If a scheduled run is due while a manual run is still in progress, the scheduled run will be skipped (misfire grace period: 5 minutes).

## Disabling the schedule

On the Schedule page, uncheck **Enable automatic scheduling** and click **Save schedule**. The schedule configuration is preserved so you can re-enable it later without retyping the expression.

Click **Remove** to delete the schedule entirely.

## Schedule persistence

The schedule is stored in `DATA_ROOT/schedule.json` and reloaded automatically when the server starts. Restarting Docker or the process does not lose the schedule.
