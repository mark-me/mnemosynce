import logging
import re
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

logger = logging.getLogger(__name__)

# Directory containing the shell scripts — always the same package directory
# as this module, regardless of where the process was launched from.
_SCRIPTS_DIR = Path(__file__).parent

# Rsync stderr lines that are warnings, not fatal errors
_RSYNC_IGNORED_ERRORS = (
    "Permission denied (13)",
    "rsync error: some files/attrs were not transferred",
)

# Type alias for the subprocess.run-compatible callable
Runner = Callable[..., subprocess.CompletedProcess]


class BackupTask:
    """Execute a configured backup task and record detailed step status.

    This class wraps the shell scripts that perform backups, retention,
    and remote sync, tracks their outcomes, and exposes a structured
    status dictionary for reporting and logging.
    """
    def __init__(
        self,
        task: dict,
        dir_local: str,
        dir_remote: str,
        work_dir: Path = None,
        runner: Runner = subprocess.run,
    ) -> None:
        """Construct a BackupTask from a task definition and backup locations.

        This stores the source and destination directories, initialises the
        status structure, configures the command runner, and writes out any
        configured exclude patterns.

        Args:
            task (dict): The task configuration dictionary containing at least ``name`` and ``dir_source``.
            dir_local (str): Local directory where backups for this task are stored.
            dir_remote (str): Remote directory (or host:dir spec) where backups are synced.
            work_dir (Path | None): Directory used for the excludes.lst file and step log files.
                Defaults to the current working directory.  Shell scripts are always
                resolved from the package directory (``_SCRIPTS_DIR``) regardless of
                this value.
            runner (Runner): Callable used to execute shell commands, mainly for testing injection.
        """
        self._name = task["name"]
        self._dir_source = task["dir_source"]
        self._dir_local = dir_local
        self._dir_remote = dir_remote
        self._status = {"name": self._name, "steps": []}
        self._scripts_dir = _SCRIPTS_DIR
        self._work_dir = work_dir or Path.cwd()
        self._runner = runner
        self._write_excludes(task.get("excludes", []))

    def _write_excludes(self, excludes: list) -> None:
        """Write the task's rsync exclude patterns to the excludes list file.

        This recreates the excludes.lst file in the working directory so
        the backup scripts can skip any paths configured to be excluded.

        Args:
            excludes (list): A list of glob-style patterns to exclude from backup.
        """
        file_excludes = self._work_dir / "excludes.lst"
        if file_excludes.exists():
            file_excludes.unlink()
        file_excludes.write_text("\n".join(excludes), encoding="utf-8")

    def start(self) -> dict:
        """Run the full backup workflow for this task and return its status.

        This records the start and end times, executes each backup step in
        sequence, and reports whether the overall task completed successfully.

        Returns:
            dict: A status dictionary describing the task run, including step details and timing.
        """
        self._status["dt_task_start"] = time.time()

        if not self._test_locations_local():
            self._status["success"] = False
            self._status["dt_task_end"] = time.time()
            return self._status

        success = self._backup()
        if success:
            success = self._apply_retention_policy()
        if success:
            success = self._test_location_remote() and self._sync_remote()

        self._status["success"] = success
        self._status["dt_task_end"] = time.time()
        return self._status

    # ------------------------------------------------------------------
    # Steps
    # ------------------------------------------------------------------

    def _backup(self) -> bool:
        """Run the main backup step for this task and return whether it succeeded.

        This invokes the backup shell script with the configured source and
        local destination directories and records the step outcome in status.

        Returns:
            bool: True if the backup script completed successfully, otherwise False.
        """
        script = self._scripts_dir / "backup.sh"
        cmd = [str(script), self._name, self._dir_local, self._dir_source]
        return self._run_step(
            step_name="backup",
            cmd=cmd,
            log_suffix="_backup.log",
            dir_from=self._dir_source,
            dir_to=self._dir_local,
            check_stderr=True,
        )

    def _apply_retention_policy(self) -> bool:
        """Apply the configured retention policy to this task's local backups.

        This invokes the retention shell script to remove older backup
        snapshots according to policy and records the step outcome in status.

        Returns:
            bool: True if the retention script completed successfully, otherwise False.
        """
        script = self._scripts_dir / "delete_old_backups.sh"
        cmd = [str(script), self._name, self._dir_local]
        return self._run_step(
            step_name="retention",
            cmd=cmd,
            log_suffix="_remove_old.log",
            dir_from=self._dir_local,
        )

    def _sync_remote(self) -> bool:
        """Synchronise this task's local backups to the remote destination.

        This invokes the remote sync shell script with the configured local
        and remote directories and records the step outcome in status.

        Returns:
            bool: True if the sync script completed successfully, otherwise False.
        """
        script = self._scripts_dir / "sync_backup_to_remote.sh"
        cmd = [str(script), self._name, self._dir_local, self._dir_remote]
        return self._run_step(
            step_name="sync",
            cmd=cmd,
            log_suffix="_sync_remote.log",
            dir_from=self._dir_local,
            dir_to=self._dir_remote,
        )

    def _run_step(
        self,
        step_name: str,
        cmd: list,
        log_suffix: str,
        dir_from: str,
        dir_to: str = None,
        check_stderr: bool = False,
    ) -> bool:
        """Execute a single backup step command and record its result.

        This runs the given shell command, interprets its success or failure
        (optionally inspecting stderr), logs any errors, and appends a
        structured step record to the task status.

        Args:
            step_name (str): Logical name of the step, such as ``"backup"`` or ``"sync"``.
            cmd (list): The command and arguments to execute via the runner.
            log_suffix (str): Suffix used to name the step-specific log file.
            dir_from (str): Source directory associated with this step.
            dir_to (str | None): Optional destination directory associated with this step.
            check_stderr (bool): Whether to treat certain rsync stderr lines as ignorable warnings.

        Returns:
            bool: True if the step completed successfully, otherwise False.
        """
        file_log = self._prepare_step_log(log_suffix)

        start_time = time.time()
        success, result = self._execute_step_command(cmd, check_stderr)

        self._log_step_result(step_name, success, result)

        self._status["steps"].append(
            {
                "step": step_name,
                "dir_from": dir_from,
                "dir_to": dir_to,
                "success": success,
                "dt_start": start_time,
                "dt_end": time.time(),
                "time_elapsed": time.strftime("%H:%M:%S", time.gmtime(time.time() - start_time)),
                "file_log": file_log,
            }
        )
        return success

    def _prepare_step_log(self, log_suffix: str) -> Path:
        """Create or reset the log file path for a step and return it.

        This constructs the step-specific log filename in the working
        directory and ensures any previous file is removed before use.
        """
        file_log = self._work_dir / (self._name + log_suffix)
        if file_log.exists():
            file_log.unlink()
        return file_log

    def _execute_step_command(
        self, cmd: list, check_stderr: bool
    ) -> tuple[bool, subprocess.CompletedProcess | None]:
        """Run the step command using the configured runner and determine success.

        This executes the command, checks the return code, optionally
        inspects stderr for ignorable rsync warnings, and returns the
        final success flag along with the CompletedProcess (if any).
        """
        try:
            result = self._runner(cmd, capture_output=True, text=True)
            success = result.returncode == 0
            if not success and check_stderr:
                success = self._stderr_has_no_fatal_errors(result.stderr)
        except subprocess.SubprocessError as exc:
            logger.error(f"Step command for task '{self._name}' raised: {exc}")
            return False, None
        return success, result

    def _log_step_result(
        self,
        step_name: str,
        success: bool,
        result: subprocess.CompletedProcess | None,
    ) -> None:
        """Log a human-readable summary of the step outcome and any stderr.

        This writes success or failure messages to the logger and, on
        failure, logs the stderr output if it is available.
        """
        if success:
            logger.info(f"Task '{self._name}' step '{step_name}' succeeded")
        else:
            logger.error(f"Task '{self._name}' step '{step_name}' failed")
            if result and result.stderr:
                logger.error(result.stderr)

    # ------------------------------------------------------------------
    # Location checks
    # ------------------------------------------------------------------

    def _test_locations_local(self) -> bool:
        """Verify that both the source and local backup locations are reachable.

        This checks that the source directory exists and that the local
        destination is available before attempting any backup work.

        Returns:
            bool: True if both locations are reachable, otherwise False.
        """
        source_ok = self._test_location(self._dir_source)
        if not source_ok:
            logger.error(f"Cannot reach back-up source '{self._dir_source}'")
        dest_ok = self._test_location(self._dir_local)
        if not dest_ok:
            logger.error(f"Cannot reach back-up local destination '{self._dir_local}'")
        return source_ok and dest_ok

    def _test_location_remote(self) -> bool:
        reachable = self._test_location(self._dir_remote)
        if not reachable:
            logger.error(f"Cannot reach back-up remote destination '{self._dir_remote}'")
        return reachable

    def _test_location(self, dir_location: str) -> bool:
        """Check that the configured remote backup destination is reachable.

        This verifies that the remote host, SSH access, and destination
        directory are available before attempting to sync backups.

        Returns:
            bool: True if the remote destination is reachable, otherwise False.
        """
        remote_pattern = re.compile(r"^(?P<user>[^@]+)@(?P<host>[^:]+):(?P<dir>.+)$")
        if match := remote_pattern.match(dir_location):
            return self._host_reachable(
                host=match["host"],
                user=match.group("user"),
                dir=match.group("dir"),
            )
        path = Path(dir_location)
        return path.is_dir()

    def _host_reachable(self, host: str, user: str, dir: str) -> bool:
        """Check that a remote host, SSH access, and directory are all reachable.

        This pings the host, tests SSH login for the given user, and verifies
        that the target directory exists before treating the remote location
        as usable for backup operations.

        Args:
            host (str): Hostname or IP address of the remote machine.
            user (str): Username to use when connecting via SSH.
            dir (str): Absolute path to the expected backup directory on the remote host.

        Returns:
            bool: True if all connectivity and directory checks succeed, otherwise False.
        """
        if self._runner(["ping", "-c 1", host], capture_output=True).returncode != 0:
            logger.error(f"Cannot reach host '{host}'")
            return False
        if (
            self._runner(["ssh", "-q", f"{user}@{host}", "exit"], capture_output=True).returncode
            != 0
        ):
            logger.error(f"Cannot ssh into server '{host}' for user '{user}'")
            return False
        if (
            self._runner(
                ["ssh", f"{user}@{host}", "test", "-d", dir], capture_output=True
            ).returncode
            != 0
        ):
            logger.error(f"Could not find directory '{dir}' on server '{host}'")
            return False
        return True

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _stderr_has_no_fatal_errors(self, stderr: str) -> bool:
        """Return True if every non-empty stderr line is a known ignorable warning."""
        success = True
        for line in stderr.split("\n"):
            if not line:
                continue
            if any(line.endswith(pat) or line.startswith(pat) for pat in _RSYNC_IGNORED_ERRORS):
                logger.warning(line)
            else:
                logger.error(line)
                success = False
        return success
