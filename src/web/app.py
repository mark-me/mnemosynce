"""Flask application factory.

Registers all blueprints including the new setup wizard, and injects the
``setup_status`` mapping into every template context so the base layout can
render the two-mode navbar without an explicit per-route lookup.
"""

import os
from pathlib import Path

from flask import Flask

from config import get_config
from config.config import BaseConfig


def create_app(config: BaseConfig = None) -> Flask:
    """Create and configure the Flask application.

    This factory registers all route blueprints, attaches a template context
    processor that exposes the current setup status, and starts the background
    scheduler when not running under test or a Werkzeug reloader child process.

    Args:
        config (BaseConfig | None): An explicit configuration object to use.
            When ``None`` the configuration is read from the ``APP_ENV``
            environment variable via :func:`config.get_config`.

    Returns:
        Flask: The fully configured Flask application instance.
    """
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder=str(Path(__file__).parent / "static"),
        static_url_path="/static",
    )

    cfg = config or get_config()
    app.config.from_object(cfg)
    cfg.ensure_dirs()

    from web.auth import bp as auth_bp
    from web.routes.config_editor import bp as config_editor_bp
    from web.routes.connections import bp as connections_bp
    from web.routes.dashboard import bp as dashboard_bp
    from web.routes.main import bp as main_bp
    from web.routes.progress import bp as progress_bp
    from web.routes.schedule import bp as schedule_bp
    from web.routes.setup_wizard import bp as setup_bp
    from web.routes.ssh_keys import bp as ssh_keys_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(setup_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(config_editor_bp)
    app.register_blueprint(connections_bp)
    app.register_blueprint(ssh_keys_bp)
    app.register_blueprint(schedule_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(progress_bp)

    # Make setup_status available in every template so base.html can switch
    # between the wizard navbar and the operations navbar without extra route
    # logic in each view function.
    @app.context_processor
    def inject_setup_status():
        """Inject the current setup readiness dict into every template context.

        Returns:
            dict: A mapping containing ``setup_status`` (the output of
            :func:`web.setup_state.get_setup_status`) and ``setup_complete``
            (a convenience boolean alias).
        """
        try:
            from web.setup_state import get_setup_status
            status = get_setup_status(app)
        except Exception:
            status = {
                "config": False,
                "ssh_key": False,
                "connection": False,
                "schedule": False,
                "complete": False,
                "has_remote_sources": False,
            }
        return {"setup_status": status, "setup_complete": status["complete"]}

    if not app.testing and os.environ.get("WERKZEUG_RUN_MAIN") != "false":
        from web.scheduler import init_scheduler
        init_scheduler(app)

    return app
