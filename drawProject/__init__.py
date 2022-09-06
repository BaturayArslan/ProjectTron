# from flask import Flask , url_for
# from . import db
# from .auth.auth import bp
# import os
#
#
# def create_app(test_config=None):
#     app = Flask(__name__, instance_relative_config=True)
#     app.config.from_mapping(
#         SECRET_KEY='hello',
#     )
#
#     if test_config is None:
#         app.config.from_pyfile("config.py", silent=True)
#     else:
#         app.config.from_mapping(test_config)
#
#     try:
#         os.makedirs(app.instance_path)
#     except OSError:
#         pass
#
#     app.register_blueprint(bp)
#
#     # register a function that clean up db connection after every request
#     #db.init_app(app)
#
#     @app.route('/hello')
#     def hello():
#         return "hello world"
#
#     return app
#
#
# if True:
#     import drawProject.views
