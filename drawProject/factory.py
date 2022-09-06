from pathlib import Path
from flask import Flask

from .auth.auth import auth_bp

def create_app():
    APP_DIR = Path(__file__)
    STATIC_FOLDER = APP_DIR / 'static'

    app = Flask(__name__, static_folder=STATIC_FOLDER)

    app.config.from_object('drawProject.config.DevConfig')

    app.register_blueprint(auth_bp)

    return app