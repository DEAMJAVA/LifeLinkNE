import os
from gunicorn.app.base import BaseApplication
from dotenv import load_dotenv

load_dotenv()


class FlaskApplication(BaseApplication):
    def __init__(self, app, options=None):
        self.application = app
        self.options = options or {}
        super().__init__()

    def load_config(self):
        for key, value in self.options.items():
            if key in self.cfg.settings and value is not None:
                self.cfg.set(key.lower(), value)

    def load(self):
        return self.application


if __name__ == "__main__":
    from app import app

    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "0.0.0.0")
    workers = int(os.environ.get("WORKERS", 2))

    options = {
        "bind": f"{host}:{port}",
        "workers": workers,
        "accesslog": "-",
        "errorlog": "-",
    }

    FlaskApplication(app, options).run()