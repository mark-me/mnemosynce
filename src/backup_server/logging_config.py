import logging
import logging.config

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "format": "%(asctime)s %(levelname)s %(message)s %(module)s %(funcName)s %(process)d",
            "class": "pythonjsonlogger.json.JsonFormatter",
        }
    },
    "handlers": {
        "stdout": {
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
            "formatter": "json",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "json",
            "filename": "log.json",
            "maxBytes": 51200,
            "backupCount": 5,
        },
    },
    "loggers": {"": {"handlers": ["stdout", "file"], "level": "WARNING"}},
}


def setup_logging() -> None:
    """Configure application-wide logging. Call once from main() before anything else."""
    logging.config.dictConfig(LOGGING)
