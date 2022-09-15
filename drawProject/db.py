import click
import os
import jwt
from quart import g, current_app
from werkzeug.local import LocalProxy
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
from flask_jwt_extended.exceptions import NoAuthorizationError
from flask_jwt_extended import decode_token
from .exceptions import DbError,BadRequest


def get_db():
    if 'db' not in g:
        g.db = AsyncIOMotorClient(
            current_app.config['MONGO_URI'],
            connectTimeoutMS=5000,
            wTimeoutMS=5000,
            maxPoolSize=100,
        )[current_app.config['DATABASE_NAME']]

    return g.db


# Reach get_db method when application context installed (I think!)
db = LocalProxy(get_db)


async def register_user(data):
    """
    data{
        "email": str,
        "username":str,
        "password": str,
        "country": str | ""
        "avatar": int

    }
    """
    aditional_info = {
        "last_login": datetime.utcnow(),
        "correnct_answer": 0,
        "total_win": 0,
        "friends": []
    }
    data.update(aditional_info)
    result = await db.users.insert_one(data)
    if result.acknowledged:
        return result
    else:
        raise DbError('Couldnt Register User.')


async def find_user(email,project):
    result = await db.users.find_one({'email': email}, {"_id": 1, "email": 1, "username": 1, "password": 1})
    if result is not None:
        return result
    else:
        raise DbError('Please Try Again.')


async def create_login_session(token, email, user_id):
    decoded_token = jwt.decode(token, current_app.config.get('JWT_SECRET_KEY'),algorithms="HS256")

    result = await db.sessions.insert_one({
        "jti": decoded_token['jti'],
        "user_email": email,
        "user_id": user_id
    })
    if result.acknowledged:
        return result
    else:
        raise DbError('Couldnt Create Session.')


async def logout_user(token):
    if token:
        decoded_token = decode_token(token)
        result = await db.sessions.delete_one({'user_email': decoded_token['sub'], 'jti': decoded_token['jti']})
        if result.deleted_count == 1:
            return True
        else:
            raise DbError('error occured when logout')
    else:
        raise BadRequest('Missing refresh token.')


async def find_refresh_token(token):
    result = await db.sessions.find_one({'user_email': token['sub'], 'jti': token['jti']}, {"_id": 1})
    if result is not None:
        return True
    else:
        raise DbError('refresh token revoked.')

#
# def close_db(e=None):
#     db = g.pop('db', None)
#
#     if db is not None:
#         db.close()
#
#
# def init_app(app):
#     app.teardown_appcontext(close_db)
