import asyncio

import quart.flask_patch
from pathlib import Path
from quart import Quart, jsonify,g,current_app,url_for,redirect,request
from quart_jwt_extended import JWTManager,get_raw_jwt,jwt_required,verify_jwt_in_request,get_jwt_claims
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import DuplicateKeyError
from collections import defaultdict
from quart_cors import cors
import aioredis
import redis.asyncio as redis

from .auth.auth import auth_bp, oauth_bp
from .rooms.rooms import rooms_bp
from .user.user import user_bp
from .game.websocket import websocket_bp
from .redis import broker,get_redis
from .error_handlers import dberror_handler,duplicate_key_handler,bad_request_handler,exception_handler,asyncio_timeout_handler,checkfailed_handler
from .exceptions import DbError,BadRequest,CheckFailed

def create_app(test=False):
    APP_DIR = Path(__file__).parent
    STATIC_FOLDER = APP_DIR / 'static'

    app = Quart(__name__, static_folder=str(STATIC_FOLDER))
    app = cors(app,allow_origin='*',allow_headers='*',allow_methods=['POST','GET'])

    if test:
        app.config.from_object('projectTron.config.TestConfig')
    else:
        app.config.from_object('projectTron.config.DevConfig')

    jwt = JWTManager(app)

    @jwt.expired_token_loader
    def my_expired_token_callback(jwt_token):
        return jsonify({"status": "error", "message": "Expired Token.","type":jwt_token['type']}), 402

    @jwt.invalid_token_loader
    def my_invalid_token_callback(message):
        return jsonify({"status": "error", "message": "Invalid Token."}), 402

    @jwt.unauthorized_loader
    def my_missing_token_callback(messge):
        return jsonify({"status": "error", "message": "Missing Token."}), 402

    app.register_error_handler(DbError,dberror_handler)
    app.register_error_handler(DuplicateKeyError,duplicate_key_handler)
    app.register_error_handler(BadRequest, bad_request_handler)
    app.register_error_handler(Exception, exception_handler)
    app.register_error_handler(asyncio.TimeoutError,asyncio_timeout_handler)
    app.register_error_handler(CheckFailed,checkfailed_handler)


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

        _,conncetion = await get_redis()
        app.add_background_task(broker.listen)
        task = list(app.background_tasks.data)[0]()
        task.set_name('background_task')
        app.my_background_task = task
        app.publish_task = None
        app.games={}
        app.game_tasks={}

    @jwt_required
    async def require_complete_login():
        """If user login with oauth provider some information about player not complete.This middleware enforce complete login."""
        if(request.method == 'OPTIONS'):
            return
        token = get_jwt_claims()
        if not token.get('user_name',None):
            return redirect(url_for('complete_login.complete'))
    

    app.before_request_funcs = defaultdict(list)
    app.before_request_funcs.update({
        'room':[require_complete_login],
        'user':[require_complete_login],
        'websocket': [require_complete_login],
    })

    app.register_blueprint(auth_bp)
    app.register_blueprint(oauth_bp)
    app.register_blueprint(rooms_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(websocket_bp)



    return app
