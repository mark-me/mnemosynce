---
icon: lucide/clock
---

# Scheduling

Backups can run on a fixed schedule using standard cron expressions, or be triggered manually from the web UI at any time. Each task can run on the global default schedule or on its own independent schedule.

## Global default schedule

Go to **Schedule** in the navigation bar (or the Schedule step of the setup wizard) and set a cron expression under **Global default schedule**. This applies to every task that does not have its own override.

Enter a five-field cron expression or pick a preset:

| Preset | Expression | Description |
|--------|-----------|-------------|
| Daily 04:00 | `0 4 * * *` | Every night at 04:00 UTC |
| Daily 22:00 | `0 22 * * *` | Every evening at 22:00 UTC |
| Weekly Sun 03:00 | `0 3 * * 0` | Sunday nights |
| Monthly 1st 04:00 | `0 4 1 * *` | First day of each month |

Check **Enable automatic scheduling** and click **Save**. The upcoming runs table updates immediately to show the next scheduled time for each task.

!!! note "All times are UTC"
    The scheduler runs in UTC. If you are in a UTC+2 timezone and want a 04:00 local run, use `0 2 * * *`.

## Per-task schedule overrides

Below the global schedule, the **Per-task overrides** section shows a card for each task. Tasks that inherit the global schedule are labelled **inherits global**. To give a task its own schedule:

1. Enter a cron expression in that task's card.
2. Check **Enable for this task**.
3. Click **Save override**.

The task card is then labelled **override** and its row in the upcoming runs table shows the task-specific cron.

To revert a task back to the global schedule, click **Reset** on its card.

!!! example "Example — different times for different tasks"
    A server backup runs at 04:00 while a desktop backup runs at 22:00 (when the desktop is most likely to be on):

    ```yaml
    schedule:
      cron: "0 4 * * *"
      enabled: true

    tasks:
      - name: Container_Data
        dir_source: /mnt/data
        # no override — inherits 04:00

      - name: Desktop_Home
        dir_source: mark@desktop-ubuntu:/home/mark
        schedule:
          cron: "0 22 * * *"
          enabled: true
    ```

    You can set this directly in `backup_config.yml` or through the Schedule page — both have the same effect.

## Cron expression reference

```
┌───────── minute  (0–59)
│ ┌─────── hour    (0–23)
│ │ ┌───── day     (1–31)
│ │ │ ┌─── month   (1–12)
│ │ │ │ ┌─ weekday (0–6, Sun=0)
│ │ │ │ │
0 4 * * *
```

Special characters: `*` any, `,` list, `-` range, `/` step.

Use [crontab.guru](https://crontab.guru) to check an expression before saving.

## Triggering a manual run

Click **Run now** on the Schedule page or the Progress page. All tasks run immediately in a background thread and you are redirected to the Progress view to watch them live.

!!! info
    A manual run does not interfere with cron schedules. If a scheduled run fires while a manual run is still in progress, it will be skipped (misfire grace period: 5 minutes).

## Disabling a schedule

Uncheck **Enable automatic scheduling** (or **Enable for this task** for an override) and click **Save**. The cron expression is preserved so you can re-enable it without retyping it.

Click **Remove** to delete the global schedule entirely, or **Reset** on a task card to remove its override and revert to the global schedule.

## Schedule persistence

Schedules are stored directly in `backup_config.yml` under the top-level `schedule` key (global) and under each task's `schedule` key (override). They are reloaded automatically when the server starts. Restarting Docker does not lose the schedule.
