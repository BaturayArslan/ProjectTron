from flask import (
    Blueprint,
    request,
    g,
    redirect,
    url_for,
    jsonify,
    make_response
)
from werkzeug.security import check_password_hash, generate_password_hash
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    JWTManager,
    jwt_required,
    get_jwt,
    get_jwt_identity,
    set_access_cookies,
    unset_jwt_cookies,
    decode_token
)
import requests
from .auth_form import RegistrationForm, LoginForm
from .auth_token import decode_auth_token, encode_auth_token
from drawProject import db

auth_bp = Blueprint("auth", __name__, url_prefix='/auth')


@auth_bp.route("/register", methods=["POST"])
def register():
    form_data = RegistrationForm(request.form)
    if form_data.validate():
        data = request.form.to_dict()
        data['password'] = generate_password_hash(data['password'])
        # TODO :: Validate X-Forwarded-For header before go production
        try:
            geolocation_data = requests.get(f"http://ip-api.com/json/{request.headers.get('X-Forwarded-For')}").json()
            data['country'] = geolocation_data['country']
        except Exception as e:
            data['country'] = ''
        try:
            db.register_user(data)
            return jsonify({
                "status": 'success',
                'message': 'registered.'
            }), 201
        # TODO :: ADD Excetpion for if user already registered before. wtih 202 error code
        except Exception as e:
            return jsonify({
                "status": "erorr",
                "message": f"{repr(e)},erorr occured when registering users to database."
            }), 503
    return jsonify({
        "status": "error",
        "message": form_data.errors
    }), 400


@auth_bp.route("/login", methods=["POST"])
def login():
    form_data = LoginForm(request.form)
    if form_data.validate():
        data = request.form.to_dict()
        try:
            user = db.login_user(data)
        except Exception as e:
            return {
                       "status": "error",
                       "message": f"{repr(e)},erorr occured related to database"
                   }, 503
        if not check_password_hash(user['password'], data['password']):
            return {
                       "status": "error",
                       "message": f"Username or Password in correct. TRY AGAIN."
                   }, 202
        access_token = create_access_token(
            identity=user['email']
        )
        refresh_token = create_refresh_token(
            identity=user['email']
        )
        insert_result = db.insert_token(refresh_token, user['email'], user['_id'])
        if not insert_result.acknowledged:
            return {'status': 'error'}, 503

        return make_response(jsonify({
            'status': "success",
            'auth_token': access_token
        }), 200)

    return jsonify({
        "status": "error",
        "message": form_data.errors
    }), 400


@auth_bp.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    token = get_jwt()
    try:
        if db.logout(token):
            return jsonify({"status":"success"}),200
    except Exception as e:
        return jsonify({"status":"error","message":"Internal Error"}),500


@auth_bp.route("/refresh", methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    refresh_token = get_jwt()
    try:
        db.find_refresh_token(refresh_token)
    except Exception as e:
        return jsonify({'status': "error", "message": 'Please login again.'}), 202

    identity = refresh_token['identity']
    accesses_token = create_access_token(identity=identity)
    return jsonify({'token': accesses_token}), 200
