# Email report

This file acts as the notification and reporting component for a backup server system, ensuring that stakeholders are promptly informed of backup results, with actionable details and supporting logs for any failures.

## Key Components

* **EmailReport Class** - The core class encapsulating all logic for composing and sending backup status reports via email. It manages email formatting, attachment handling, and recipient management.
* **Initialization (__init__)**
    * Sets up the logging database connection.
    * Configures sender/recipient email addresses and credentials.
    * Loads Jinja2 templates for HTML and plain-text email bodies.
* **send_mail**
    * Public method to send a report email.
    * Composes the email using task status data and sends it via Gmail's SMTP server.
    * Handles logging of success or failure in sending the email.
* **_compose_mail**
    * Assembles the email content, including subject, recipients, and body (both HTML and plain text).
    * Attaches log files if any task steps failed.
    * Uses templates to render the email body with task status data.
* **_add_attachment**
    * Zips a given file and attaches it to the email.
    * Ensures that attachments are compressed and named appropriately.
* **__enrich_task_status**
    * Enhances the provided task status list with additional metadata:
        * Calculates elapsed times and last successful run statistics.
        * Ensures all expected steps are represented, even if not executed.
        * Formats timestamps for readability.
* **Integration with Other Modules**
    * Uses a LogDB class (from database) to fetch historical task data.
    * Relies on a custom logging configuration for error and info reporting.
* **Templating and Attachments**
    * Employs Jinja2 for flexible, maintainable email formatting.
    * Attaches both general and step-specific log files to aid in troubleshooting.
