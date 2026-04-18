# Config file

## Overview

This file, `config_file.py`, is responsible for loading, validating, and providing access to the backup server's configuration data, which is stored in a YAML file. It ensures that the configuration file exists, contains all required top-level entries, and that each backup task is properly structured. The file also integrates logging to provide feedback and error reporting during configuration processing.

## Key Components

* **Imports:**
    * Uses `pathlib.Path` for file path handling.
    * Uses `yaml` for parsing YAML configuration files.
    * Imports a custom logging setup from `logging_config`.
* **ConfigFile Class:**
    * **Purpose**: Encapsulates all logic for reading and validating the backup server's configuration file.
    * **`Constructor (__init__)`**: Accepts the path to the configuration file and initializes internal state.
    * **`read()` Method:**
        * Loads the YAML configuration file.
        * Validates the presence of required top-level configuration entries.
        * Validates the structure of each backup task.
        * Returns the parsed configuration as a dictionary.
    * **`_check_minimal_requirements()` Method:**
        * Ensures required configuration keys (`dir_backup_local`, `dir_backup_remote`, `email_report`, `tasks`) are present.
        * Handles optional `email_admin` logic.
        * Raises exceptions and logs errors if requirements are not met.
    * **`_check_tasks_structure()` Method:**
        * Iterates through each task in the configuration.
        * Ensures each task has required fields (name, dir_source).
        * Logs warnings if optional fields (like excludes) are missing.
  * **Logging:** - Provides informative logs for successful operations, warnings for missing optional fields, and errors for missing required fields.
