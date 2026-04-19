# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:python3.13-alpine

ARG APP_VERSION=dev
ENV APP_VERSION=${APP_VERSION} \
    APP_ENV=production \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Install system dependencies:
#   bash    — the shell scripts require bash, not just sh
#   rsync   — used by backup.sh and sync_backup_to_remote.sh
#   openssh — ssh and ssh-keygen for key management and remote checks
RUN apk add --no-cache bash rsync openssh-client

WORKDIR /app

# Install Python dependencies via uv (leverages layer cache)
COPY pyproject.toml uv.lock ./

# Copy application source
COPY src/ ./src/

# Copy the README for easy access in the container (optional, but can be helpful for debugging or reference)
COPY README.md ./

RUN uv sync --frozen --no-dev


# Make the shell scripts (now part of the backup_server package) executable.
# They are already copied in via COPY src/ above.
RUN chmod +x src/backup_server/backup.sh \
             src/backup_server/delete_old_backups.sh \
             src/backup_server/sync_backup_to_remote.sh

# /data is the single mount point for all persistent state:
#   backup_config.yml, log.db, log.json, ssh keys
VOLUME ["/data"]

EXPOSE 5000

# Run the Flask app via uv so the virtualenv is activated correctly.
# Gunicorn is used in production for proper request handling.
CMD ["uv", "run", "gunicorn", \
    "--bind", "0.0.0.0:5000", \
    "--workers", "2", \
    "--timeout", "120", \
    "web.app:create_app()"]
