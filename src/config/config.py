"""Application configuration.

Selects the right config class based on the APP_ENV environment variable:

    development  (default) — debug on, login bypassed, uses local .env
    test                   — isolated paths, used by pytest
    production             — debug off, login enforced, all values from env vars

Usage in the Flask factory::

    from config import get_config
    app.config.from_object(get_config())
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root in development only.
# In production the container sets env vars directly — no .env file is used.
if os.getenv("APP_ENV", "development") != "production":
    _project_root = Path(__file__).parent.parent.parent
    load_dotenv(_project_root / ".env")


class BaseConfig:
    """Settings shared across all environments."""

    APP_ENV: str = os.getenv("APP_ENV", "development")

    # --- Persistent data root (mounted as a volume in production) ---
    DATA_ROOT: Path = Path(os.getenv("DATA_ROOT", "/data"))

    # Derived paths — never override these directly
    CONFIG_PATH: Path = DATA_ROOT / "backup_config.yml"
    DB_PATH: Path = DATA_ROOT / "log.db"
    SSH_KEY_DIR: Path = DATA_ROOT / "ssh"

    # --- Flask ---
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-change-in-production")

    # --- Authentication ---
    # Single admin account. In production, set via environment variable / nix-sops.
    ADMIN_USER: str = os.getenv("ADMIN_USER", "admin")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "dev-password")

    # --- Email (Gmail) ---
    GMAIL_ADDRESS: str = os.getenv("GMAIL_ADDRESS", "")
    GMAIL_PASSWORD: str = os.getenv("GMAIL_PASSWORD", "")

    @classmethod
    def ensure_dirs(cls) -> None:
        """Create all required data directories if they do not exist.

        Call once at application startup before anything tries to write data.
        """
        cls.DATA_ROOT.mkdir(parents=True, exist_ok=True)
        cls.SSH_KEY_DIR.mkdir(parents=True, exist_ok=True)


class DevelopmentConfig(BaseConfig):
    """Local development: debug on, login bypassed."""

    DEBUG: bool = True
    # Override DATA_ROOT to a local dev directory so we don't need /data to exist
    DATA_ROOT: Path = Path(os.getenv("DATA_ROOT", Path(__file__).parent.parent.parent / "dev-data"))
    CONFIG_PATH: Path = DATA_ROOT / "backup_config.yml"
    DB_PATH: Path = DATA_ROOT / "log.db"
    SSH_KEY_DIR: Path = DATA_ROOT / "ssh"


class TestConfig(BaseConfig):
    """Isolated paths for pytest — never touches dev or production data."""

    DEBUG: bool = True
    TESTING: bool = True
    DATA_ROOT: Path = Path("/tmp/backup-server-test-data")
    CONFIG_PATH: Path = DATA_ROOT / "backup_config.yml"
    DB_PATH: Path = DATA_ROOT / "log.db"
    SSH_KEY_DIR: Path = DATA_ROOT / "ssh"
    ADMIN_PASSWORD: str = "test-password"
    SECRET_KEY: str = "test-secret"
    GMAIL_ADDRESS: str = "test@example.com"
    GMAIL_PASSWORD: str = "test-gmail-password"


class ProductionConfig(BaseConfig):
    """Production: debug off, login enforced, all secrets from environment."""

    DEBUG: bool = False

    def __init__(self) -> None:
        # Refuse to start with default placeholder values in production.
        if self.SECRET_KEY == "dev-secret-change-in-production":
            raise RuntimeError("SECRET_KEY must be set in production.")
        if self.ADMIN_PASSWORD == "dev-password":
            raise RuntimeError("ADMIN_PASSWORD must be set in production.")


_ENV_MAP = {
    "development": DevelopmentConfig,
    "test": TestConfig,
    "production": ProductionConfig,
}


def get_config() -> BaseConfig:
    """Return the config instance matching the current APP_ENV."""
    env = os.getenv("APP_ENV", "development")
    cls = _ENV_MAP.get(env)
    if cls is None:
        raise ValueError(f"Unknown APP_ENV '{env}'. Must be one of: {list(_ENV_MAP)}")
    return cls()
