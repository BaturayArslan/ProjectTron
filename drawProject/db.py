import click
import os
import jwt
from flask import g, current_app
from werkzeug.local import LocalProxy
from pymongo import MongoClient
from datetime import datetime


def get_db():
    if 'db' not in g:
        g.db = MongoClient(
            current_app.config['MONGO_URI'],
            connectTimeoutMS=5000,
            wTimeoutMS=5000,
            maxPoolSize=100,
        )[current_app.config['DATABASE_NAME']]

    return g.db


# Reach get_db method when application context installed (I think!)
db = LocalProxy(get_db)


def register_user(data):
    aditional_info = {
        "last_login": datetime.utcnow(),
        "correnct_answer": 0,
        "total_win": 0,
        "friends": []
    }
    data.update(aditional_info)
    data.pop('confirm')
    get_db().users.insert_one(data)


def login_user(data):
    result = db.users.find_one({'email': data['email']}, {"_id": 1, "email": 1, "username": 1, "password": 1})
    return result


def insert_token(token, email, user_id):
    decoded_token = jwt.decode(token, current_app.config.get('JWT_SECRET_KEY'))

    result = db.sessions.insert_one({
        "jti": decoded_token['jti'],
        "user_email": email,
        "user_id": user_id
    })
    return result


def logout_user(token):
    result = db.sessions.delete_one({'user_email': token['sub'], 'jti': token['jti']})
    if result.deleted_count == 1:
        return True
    else:
        raise Exception('error occured when logout')


def find_refresh_token(token):
    result = db.sessions.find_one({'user_email': token['sub'], 'jti': token['jti']}, {"_id": 1})
    if result.acknowledged:
        return True
    else:
        raise Exception('refresh token revoked.')

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
