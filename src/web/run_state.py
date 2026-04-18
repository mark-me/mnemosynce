"""Shared run state for the progress view.

A single RunState instance tracks whether a backup is currently running,
collects log lines as they arrive, and records which steps have completed.

Both the scheduler thread (writer) and the SSE stream (reader) access this
object.  All mutations are protected by a threading.Lock so reads from the
Flask request thread are always consistent.

The log buffer is capped at MAX_LINES to avoid unbounded memory growth.
"""

import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime

MAX_LINES = 2000

# Step names in execution order — used to derive status badges
STEP_NAMES = ("backup", "retention", "sync")


@dataclass
class StepStatus:
    """Track the progress state for a single backup step.

    This records whether the step is pending, running, succeeded, or failed,
    and captures simple string timestamps for when it started and ended.

    Attributes:
        name (str): The logical name of the step, such as "backup" or "sync".
        state (str): The current state of the step: "pending", "running", "success", or "failed".
        started (str | None): The time the step entered the running state, or None if not started.
        ended (str | None): The time the step finished, or None if it has not yet completed.
    """
    name: str
    state: str = "pending"   # pending | running | success | failed
    started: str | None = None
    ended: str | None = None


@dataclass
class RunState:
    """Hold shared backup run progress for use by the live progress view.

    This tracks whether a backup is active, which task is running, the
    overall timing and success state, and a rolling buffer of log lines
    and per-step status that can be safely read from other threads.

    Attributes:
        active (bool): Whether a backup run is currently in progress.
        task_name (str | None): A short label for the task being executed.
        started (str | None): The time the current run started, or None if idle.
        ended (str | None): The time the current run finished, or None if still running.
        success (str | None): True if the last run finished successfully, False if it failed, or None if unknown.
        steps (list): An ordered list of StepStatus objects describing each logical step in the run.
        _lines (list): The buffered log lines associated with the current or last run.
        _lock (threading.Lock): A threading lock that guards all mutations and reads of the state.
        _seq (int): A monotonically increasing sequence number used by readers to fetch incremental updates.
    """
    active: bool = False
    task_name: str | None = None
    started: str | None = None
    ended: str | None = None
    success: str | None = None
    steps: list = field(default_factory=list)
    _lines: list = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    # Monotonically increasing sequence number — readers track where they are
    _seq: int = 0

    def start(self, task_name: str) -> None:
        """Begin tracking a new backup run with an initial clean state.

        This marks the run as active, records the task name and start time,
        resets any previous results, and initialises step and log tracking.

        Args:
            task_name (str): A short identifier for the backup task being started.
        """
        with self._lock:
            self.active = True
            self.task_name = task_name
            self.started = _now()
            self.ended = None
            self.success = None
            self.steps = [StepStatus(name=s) for s in STEP_NAMES]
            self._lines = []
            self._seq = 0

    def finish(self, success: bool) -> None:
        """Mark the current backup run as finished with a final outcome.

        This records the end time, sets the success flag, and marks the run
        as no longer active so readers know the run has completed.

        Args:
            success (bool): True if the run completed successfully, False if it failed.
        """
        with self._lock:
            self.active = False
            self.ended = _now()
            self.success = success

    def add_line(self, line: str) -> None:
        """Append a new log line to the rolling buffer and bump the sequence.

        This maintains the buffer within the MAX_LINES cap and increments
        the sequence counter so readers can detect that new output is available.

        Args:
            line (str): The log message text to add to the current run.
        """
        with self._lock:
            if len(self._lines) >= MAX_LINES:
                self._lines.pop(0)
            self._lines.append(line)
            self._seq += 1

    def step_running(self, step_name: str) -> None:
        """Mark a named step as currently running and record its start time.

        This updates the matching step's state and timestamp so readers
        can see which part of the backup is in progress.

        Args:
            step_name (str): The logical name of the step entering the running state.
        """
        with self._lock:
            for s in self.steps:
                if s.name == step_name:
                    s.state = "running"
                    s.started = _now()

    def step_done(self, step_name: str, success: bool) -> None:
        """Mark a named step as finished and record its final outcome.

        This updates the matching step's state to success or failed and
        stores the time it completed so readers can see how it ended.

        Args:
            step_name (str): The logical name of the step that has finished.
            success (bool): True if the step completed successfully, False if it failed.
        """
        with self._lock:
            for s in self.steps:
                if s.name == step_name:
                    s.state = "success" if success else "failed"
                    s.ended = _now()

    def snapshot(self) -> dict:
        """Return a read-only snapshot of the current run state as a dictionary.

        This captures the active flag, timings, per-step statuses, and sequence
        number so callers can render a consistent view without holding the lock.

        Returns:
            dict: A serialisable dictionary representing the current run state.
        """
        with self._lock:
            return {
                "active": self.active,
                "task_name": self.task_name,
                "started": self.started,
                "ended": self.ended,
                "success": self.success,
                "steps": [
                    {"name": s.name, "state": s.state,
                     "started": s.started, "ended": s.ended}
                    for s in self.steps
                ],
                "seq": self._seq,
            }

    def lines_from(self, seq: int) -> tuple[list[str], int]:
        """Return log lines after a given sequence number and the latest sequence.

        This lets callers efficiently fetch only new output since their last
        poll, using the sequence counter to compute the correct slice.

        Args:
            seq (int): The last sequence number the caller has seen.

        Returns:
            tuple[list[str], int]: A pair of the new log lines and the current sequence number.
        """
        with self._lock:
            current = len(self._lines)
            offset = max(0, current - (self._seq - seq))
            return list(self._lines[offset:]), self._seq


def _now() -> str:
    """Return the current time in a compact, human-friendly string format.

    This is used to timestamp run and step events with a simple HH:MM:SS
    representation in UTC suitable for display in the progress view.

    Returns:
        str: The current UTC time formatted as ``HH:MM:SS``.
    """
    return datetime.now(tz=UTC).strftime("%H:%M:%S")


# Module-level singleton — imported by scheduler and routes
state = RunState()
