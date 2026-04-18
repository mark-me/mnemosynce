import logging
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


class ConfigFile:
    """Load and validate backup configuration from a YAML file on disk.

    This helper encapsulates reading the config, checking that required
    fields and task definitions are present, and exposing the resulting
    dictionary to the rest of the backup server.
    """

    def __init__(self, file_config: str):
        """Initialise a ConfigFile wrapper around a YAML backup configuration.

        This stores the path to the configuration file and prepares an empty
        in-memory dictionary that will later hold the parsed configuration.

        Args:
            file_config (str): Filesystem path to the YAML backup configuration file.
        """
        self._file_config = Path(file_config)
        self.backup_config = {}

    def read(self) -> dict:
        """Load and validate the backup configuration from the YAML file.

        This parses the config file into a Python dictionary, checks that
        all required top-level and task-level fields are present, and
        returns the validated configuration for use by the backup runner.

        Returns:
            dict: The fully validated backup configuration loaded from disk.

        Raises:
            FileNotFoundError: If the configuration file does not exist.
            KeyError: If required configuration keys are missing.
        """
        if not self._file_config.exists():
            msg = f"Config file '{self._file_config}' does not exist."
            logger.error(msg)
            raise FileNotFoundError(msg)
        logger.info(f"Reading backup config from '{self._file_config}'")
        with open(self._file_config, encoding="utf-8") as file:
            self.backup_config = yaml.load(file, Loader=yaml.Loader)
        self._check_minimal_requirements()
        self._check_tasks_structure()
        return self.backup_config

    def _assert_keys(self, d: dict, required_keys: list, context: str) -> None:
        """Raise if any required keys are missing from d.

        Args:
            d (dict): The dictionary to check.
            required_keys (list): Keys that must be present.
            context (str): Human-readable label used in the error message.
        """
        if missing := [k for k in required_keys if k not in d]:
            msg = f"Missing entries {missing} in {context}"
            logger.error(msg)
            raise KeyError(msg)

    def _check_minimal_requirements(self) -> None:
        """Validate that the top-level backup configuration has all required fields.

        This checks for mandatory keys such as backup directories, email addresses,
        and the task list, and normalises the optional admin email setting.

        Raises:
            KeyError: If any of the required top-level configuration keys are missing.
        """
        self._assert_keys(
            self.backup_config,
            ["dir_backup_local", "dir_backup_remote", "email_sender", "email_report", "tasks"],
            context=f"file '{self._file_config}'",
        )
        # Admin email defaults to empty when absent or same as report address
        if "email_admin" not in self.backup_config:
            self.backup_config["email_admin"] = ""
        elif self.backup_config["email_admin"] == self.backup_config["email_report"]:
            self.backup_config["email_admin"] = ""

    def _check_tasks_structure(self) -> None:
        """Validate the structure of each task entry in the backup configuration.

        This ensures required fields are present for every task and logs
        helpful information or warnings when optional fields are missing.

        Raises:
            KeyError: If any task is missing mandatory keys such as ``name`` or ``dir_source``.
        """
        for task in self.backup_config["tasks"]:
            logger.info(f"Found task '{task['name']}'")
            self._assert_keys(
                task,
                ["name", "dir_source"],
                context=f"task in file '{self._file_config}'",
            )
            if "excludes" not in task:
                logger.warning(f"No excludes defined for task '{task['name']}'")
