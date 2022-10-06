import quart.flask_patch
from pathlib import Path
from quart import Quart, jsonify,g,current_app
from flask_jwt_extended import JWTManager
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio
import aioredis

from .auth.auth import auth_bp, oauth_bp
from .rooms.rooms import rooms_bp
from .user.user import user_bp
from .game.websocket import websocket_bp
from .redis import broker,get_redis

def create_app(test=False):
    APP_DIR = Path(__file__).parent
    STATIC_FOLDER = APP_DIR / 'static'

    app = Quart(__name__, static_folder=str(STATIC_FOLDER))
    if test:
        app.config.from_object('drawProject.config.TestConfig')
    else:
        app.config.from_object('drawProject.config.DevConfig')

    jwt = JWTManager(app)

    @jwt.expired_token_loader
    def my_expired_token_callback(jwt_header, jwt_paylaod):
        return jsonify({"status": "error", "message": "Expired Token."}), 402

    @jwt.invalid_token_loader
    def my_invalid_token_callback(message):
        return jsonify({"status": "error", "message": "Invalid Token."}), 402

    @jwt.unauthorized_loader
    def my_missing_token_callback(messge):
        return jsonify({"status": "error", "message": "Missing Token."}), 402

    @app.before_first_request
    async def init():

        app.redis_connection_pool = await aioredis.from_url(current_app.config['REDIS_URL'], port=6379,
                                             username='default', password=current_app.config['REDIS_PASSWORD'])
        app.database_connection_pool = AsyncIOMotorClient(
            current_app.config['MONGO_URI'],
            connectTimeoutMS=5000,
            wTimeoutMS=5000,
            maxPoolSize=10,
        )[current_app.config['DATABASE_NAME']]
        await get_redis()
        app.add_background_task(broker.listen)
        task = list(app.background_tasks.data)[0]()
        task.set_name('background_task')
        app.my_background_task = task
        app.publish_task = None
        app.games={}
        app.game_tasks={}



    # @app.after_serving
    # async def clear():
    #     app.my_background_task.cancel()
    #     await app.my_background_task


    app.register_blueprint(auth_bp)
    app.register_blueprint(oauth_bp)
    app.register_blueprint(rooms_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(websocket_bp)


    return app
