# Backup task

## Overview

This file defines the BackupTask class, which encapsulates the logic for executing a backup workflow in a server environment. The class manages the process of backing up data from a source directory to a local backup location, applying a retention policy to remove old backups, and synchronizing the backups to a remote location. It also handles error logging, status tracking, and validation of backup locations (both local and remote).

The file is designed to be a core component of a backup server system, orchestrating the execution of shell scripts for backup, retention, and synchronization, while providing detailed status and error reporting for each step.

## Key Components

* **BackupTask Class** -
    The central class that manages the lifecycle of a backup task. It is initialized with task configuration and directory paths, and exposes a start() method to execute the full backup workflow.

* **start() Method** - Orchestrates the backup process, including:
    * Validating local and remote locations.
    * Running the backup script.
    * Applying the retention policy.
    * Synchronizing to the remote location.
    * Collecting and returning detailed status for each step.
* **Shell Script Integration** -
The class delegates actual backup, retention, and sync operations to external shell scripts (`backup.sh`, `delete_old_backups.sh`, `sync_backup_to_remote.sh`), capturing their output and return codes to determine success or failure.
* **Location Testing Methods** -
Methods like `_test_location`, `_test_locations_local`, and `_test_location_remote` check the accessibility of source, local, and remote directories. For remote locations, it performs ping, SSH, and directory existence checks.
* **Error Handling and Logging** -
Uses a logger (from an external `logging_config` module) to record information, warnings, and errors throughout the process. The `_stderr_has_error` method parses script stderr output to distinguish between critical and non-critical errors.
* **Status Tracking** -
Each step's outcome is recorded in a status dictionary, including timing, success state, and log file references, via the `_step_status` method.
* **Excludes File Management** -
Handles the creation and cleanup of an `excludes.lst` file, which is used to specify files or directories to exclude from the backup.

