import click
from flask import g, current_app
from flask_pymongo import PyMongo


def get_db():
    if 'db' not in g:
        g.db = PyMongo(current_app).db

    return g.db


def close_db(e=None):
    db = g.pop('db', None)

    if db is not None:
        db.close()


def init_app(app):
    app.teardown_appcontext(close_db)
