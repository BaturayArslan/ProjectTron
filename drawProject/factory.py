from pathlib import Path
from flask import Flask
from flask_jwt_extended import JWTManager

from .auth.auth import auth_bp,oauth_bp

def create_app(test=False):
    APP_DIR = Path(__file__).parent
    STATIC_FOLDER = APP_DIR / 'static'

    app = Flask(__name__,static_folder=STATIC_FOLDER)

    if test:
        app.config.from_object('drawProject.config.TestConfig')
    else:
        app.config.from_object('drawProject.config.DevConfig')

    jwt = JWTManager(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(oauth_bp)

    return app