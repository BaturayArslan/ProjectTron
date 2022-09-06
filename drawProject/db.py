import click
import os
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
    get_db().users.insert_one(data)

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
