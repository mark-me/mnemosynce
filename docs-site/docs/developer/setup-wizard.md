---
icon: lucide/wand
---

# Setup wizard internals

The setup wizard is implemented across three modules that together answer one question on every request: *has this user finished setting up the application?*

## Module responsibilities

| Module | Responsibility |
|--------|---------------|
| `setup_state.py` | Derives readiness from disk + session; exposes `get_setup_status()` and `is_setup_complete()` |
| `setup_guard.py` | `setup_complete_required` decorator — redirects to `/setup/` when incomplete |
| `routes/setup_wizard.py` | Flask blueprint — four step pages + `POST /setup/complete` |

---

## `setup_state.py`

### The four checks

Each check is evaluated freshly on every call to `get_setup_status()`. Checks 1, 2, and 4 read the filesystem; check 3 reads the Flask session.

#### 1. `config`

`_check_config(app)` returns `True` when:

- `CONFIG_PATH` exists, and
- it parses as valid YAML, and
- all five required keys are present: `dir_backup_local`, `dir_backup_remote`, `email_sender`, `email_report`, `tasks`.

The same structural check is used by the config editor route before saving — the web UI and the setup state are always in agreement.

#### 2. `ssh_key`

`_check_ssh_key(app)` returns `True` when at least one `*.pub` file in `SSH_KEY_DIR` has a matching private key file alongside it.

**Auto-satisfied** when `has_remote_sources` is `False` (all task sources are local paths).

#### 3. `connection`

`_connection_tested()` returns `True` when `session["setup_connection_tested"]` is truthy.

This flag is written by `mark_connection_tested()`, which is called from `connections.test_ssh` and `connections.test_email` after any successful test.

**Auto-satisfied** when `has_remote_sources` is `False`.

#### 4. `schedule`

`_check_schedule(app)` returns `True` when `DATA_ROOT/schedule.json` exists and its `"enabled"` field is truthy.

### `has_remote_sources`

`_has_remote_sources(app)` scans the `tasks` list in the saved config and returns `True` if any `dir_source` contains `@` (i.e. `user@host:/path` form). This drives the skip logic for steps 2 and 3.

### Completion logic

```python
complete = (config_ok and ssh_ok and connection_ok and schedule_ok) \
           or session.get("setup_explicitly_complete")
```

Two independent paths reach `complete = True`:

- **Automatic** — all four checks pass simultaneously (re-evaluated on every request).
- **Explicit** — the user clicked **Finish setup anyway**, which sets `session["setup_explicitly_complete"]` via `mark_setup_complete()`.

### Session scope

Because completion state lives in the browser session, it resets when:

- The server restarts (Flask sessions are signed with `SECRET_KEY` but not server-side — losing the key invalidates all sessions).
- The user logs out (`session.clear()`).
- The cookie expires.

After a reset, `is_setup_complete()` re-evaluates the filesystem checks. If config, SSH key, and schedule are all still on disk, setup is automatically complete again — the only check that requires re-doing is the connection test (which has no on-disk representation).

---

## `setup_guard.py`

```python
@setup_complete_required
def my_view():
    ...
```

The decorator calls `is_setup_complete(app)` and redirects to `url_for("setup.index")` if it returns `False`. It is applied **after** `@login_required` in the decorator stack, so the evaluation order is:

```
request → @login_required → @setup_complete_required → view function
```

Unauthenticated users hit the login wall before the setup check — they never see the wizard URL directly.

### Which routes are gated

| Route | Gated |
|-------|-------|
| `dashboard.index`, `dashboard.history` | Yes |
| `progress.index`, `progress.state_json`, `progress.stream` | Yes |
| `schedule.index`, `schedule.run_now`, `schedule.status` | Yes |
| `schedule.save`, `schedule.remove` | **No** — wizard step 4 uses these |
| `config_editor.*`, `connections.*`, `ssh_keys.*` | **No** — used during wizard |
| `setup.*` | **No** — would cause a redirect loop |

---

## `routes/setup_wizard.py`

### Blueprint

Registered at `/setup`. All routes require `@login_required` but are explicitly excluded from `setup_complete_required`.

### Step routing

`/setup/` (index) reads `get_setup_status()`, builds the list of visible steps via `_visible_steps(has_remote)`, finds the first incomplete one, and redirects there. If setup is already complete it redirects to the dashboard.

Steps 2 and 3 (`/setup/ssh-keys` and `/setup/connections`) redirect themselves to `/setup/schedule` when `has_remote_sources` is `False` — they never render.

### `?next=` parameter

Wizard step templates post forms to the **existing** route handlers for config, SSH keys, and schedule, not to new wizard-specific endpoints. Each form action includes `?next=<current-wizard-step-url>`:

```html
<form method="post"
      action="{{ url_for('config_editor.save') }}?next={{ url_for('setup.step_config') }}">
```

The underlying route handlers (`config_editor.save`, `ssh_keys.generate`, `ssh_keys.delete`, `schedule.save`, `schedule.remove`) honour this parameter:

```python
next_url = request.args.get("next") or url_for("config_editor.editor")
return redirect(next_url)
```

This avoids duplicating the save/validate logic in the wizard and keeps the standalone pages fully functional at the same time.

### Finish endpoint

`POST /setup/complete` calls `mark_setup_complete()` and redirects to the dashboard. It is the target of the **Finish setup** and **Finish setup anyway** buttons on the Schedule step.

### Stepper state

Each step template extends `wizard_base.html`, which renders the horizontal stepper bar. The stepper receives:

| Variable | Type | Source |
|----------|------|--------|
| `wizard_steps` | `list[dict]` | `_visible_steps(has_remote_sources)` |
| `wizard_current` | `int` | `_current_step_index(status, steps)` |
| `setup_status` | `dict` | `get_setup_status(app)` |

Steps before `wizard_current` render with a green check bubble; the active step renders with a blue outlined bubble; future steps render grey.

---

## Adding a new setup step

1. Add an entry to `WIZARD_STEPS` in `routes/setup_wizard.py` with a unique `id`, `label`, `icon`, and `route`.
2. Add the corresponding check to `setup_state.py` — a filesystem or session check that returns a `bool`.
3. Include the new `id` in the `complete` calculation in `get_setup_status()`.
4. Create the route function and template (extending `wizard_base.html`, filling `{% block wizard_content %}`).
5. If the step can be skipped under certain conditions, add the skip logic inside the route function (redirect to the next step's URL).
6. Add tests in `tests/test_setup_wizard.py` covering the new check and the HTTP behaviour.
