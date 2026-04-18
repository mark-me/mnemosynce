"""Flask application factory."""

from pathlib import Path

from flask import Flask

from config import get_config
from config.config import BaseConfig


def create_app(config: BaseConfig = None) -> Flask:
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
    from web.routes.ssh_keys import bp as ssh_keys_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(config_editor_bp)
    app.register_blueprint(connections_bp)
    app.register_blueprint(ssh_keys_bp)
    app.register_blueprint(schedule_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(progress_bp)

    import os
    if not app.testing and os.environ.get("WERKZEUG_RUN_MAIN") != "false":
        from web.scheduler import init_scheduler
        init_scheduler(app)

    return app
