import os
from datetime import timedelta

from flask import Flask, g, render_template

from config import Config
from models import build_db_from_config
from auth import current_user
from data import location_display_name

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.permanent_session_lifetime = timedelta(
        days=config_class.PERMANENT_SESSION_LIFETIME_DAYS
    )

    db = build_db_from_config(config_class)

    @app.before_request
    def _attach_db():
        g.db = db

    @app.context_processor
    def _inject_user():
        return {
            "current_user": current_user(),
            "location_display_name": location_display_name,
        }

    from routes.auth_routes import bp as auth_bp
    from routes.dashboard_routes import bp as dashboard_bp
    from routes.api_routes import bp as api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(api_bp)

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("error.html", code=403,
                                message="You don't have permission to do that."), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("error.html", code=404,
                                message="Page not found."), 404

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
