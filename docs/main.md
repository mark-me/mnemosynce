# Main

## Overview

This file serves as the main entry point for a backup server application. Its primary responsibilities are to orchestrate the backup process, manage logging, and handle reporting. The script reads configuration settings, executes backup tasks, logs their outcomes, sends summary reports via email, and performs cleanup of log files after execution. It ties together several components of the system, acting as the central coordinator for a complete backup run.

## Key Components

* **Imports and Logging Setup** - Imports essential modules and sets up a logger for the script. It brings in custom classes for backup tasks, configuration management, database logging, email reporting, and logging configuration.
* **delete_logs(lst_task_status: list)** - A utility function that removes log files and their zipped versions associated with each backup task step, as well as a general application log archive. This helps maintain a clean working directory after each backup run.
* **main(file_config: str)** - The core function that:
    * Initializes the log database.
    * Reads backup configuration from a specified file.
    * Iterates over all defined backup tasks, executing each and recording their status.
    * Sends an email report summarizing the backup run.
    * Cleans up log files generated during the process.
* **Script Entry Point** - The `if __name__ == "__main__":` block ensures the script can be run directly, accepting a configuration file path as a command-line argument.

This file is crucial in the larger system as it coordinates the execution flow, integrates with other modules, and ensures that each backup cycle is fully managed from start to finish.
