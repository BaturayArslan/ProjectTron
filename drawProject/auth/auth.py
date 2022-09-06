from flask import Blueprint, request, g, redirect, url_for
from werkzeug.security import check_password_hash, generate_password_hash
import requests

from .auth_form import RegistrationForm, LoginForm
from drawProject import db

auth_bp = Blueprint("auth", __name__, url_prefix='/auth')


@auth_bp.route("/register", methods=["POST"])
def register():
    form_data = RegistrationForm(request.form)
    if form_data.validate():
        data = request.form.to_dict()
        data['password'] = generate_password_hash(data['password'])
        #TODO :: Validate X-Forwarded-For header before go production
        try:
            geolocation_data = requests.get(f"http://ip-api.com/json/{request.headers.get('X-Forwarded-For')}").json()
            data['country'] = geolocation_data['country']
        except Exception as e :
            data['country'] = ''
        try:
            db.register_user(data)
            return redirect(url_for('auth.login')),301
        except Exception as e:
            return {
                "erorr": "erorr occured when registering users to database.",
                "message": f"{repr(e)}"
            },503
    return {
        "error": "error occured when registering user.",
        "message": form_data.errors
    },400


@auth_bp.route("/login", methods=["POST", "GET"])
def login():
    form_data = LoginForm(request.form)
    db = get_db()
    if form_data.validate():
        data = request.form.to_dict()
        try:
            user = db.users.find_one({'email': data['email']}, {"_id": 1, "email": 1, "username": 1, "password": 1})
        except Exception as e:
            return {
                "erorr": "erorr occured related to database",
                "message": f"{repr(e)}"
            }
        if not check_password_hash(user['password'], data['password']):
            return {
                "erorr": "Login error",
                "message": f"Username or Password in correct. TRY AGAIN."
            }
