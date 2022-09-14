from pathlib import Path
from flask import Flask, jsonify
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

    @jwt.expired_token_loader
    def my_expired_token_callback(jwt_header,jwt_paylaod):
        return jsonify({"status":"error","message":"Expired Token."}),402

    @jwt.invalid_token_loader
    def my_invalid_token_callback(message):
        return jsonify({"status":"error","message":"Invalid Token."}),402

    @jwt.unauthorized_loader
    def my_missing_token_callback(messge):
        return jsonify({"status":"error","message":"Missing Token."}),402

    @app.before_request
    def hello():
        pass
    app.register_blueprint(auth_bp)
    app.register_blueprint(oauth_bp)

    return app