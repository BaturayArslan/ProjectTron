from quart import (
    Blueprint,
    request,
    g,
    redirect,
    url_for,
    jsonify,
    make_response,
    current_app,
)
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    JWTManager,
    jwt_required,
    get_jwt,
    get_jwt_identity,
    set_access_cookies,
    unset_jwt_cookies,
    decode_token,

)
# from flask_jwt_extended.exceptions
from werkzeug.security import check_password_hash, generate_password_hash
from rauth.service import OAuth2Service
from pymongo.errors import DuplicateKeyError
import requests
import json
from .auth_form import RegistrationForm, LoginForm, CompleteLoginForm
from .auth_token import decode_auth_token, encode_auth_token
from ..exceptions import BadRequest, DbError
from projectTron import db

auth_bp = Blueprint("auth", __name__, url_prefix='/auth')
oauth_bp = Blueprint('oauth', __name__, url_prefix='/oauth')
complete_login_bp = Blueprint('complete_login',__name__,url_prefix='/complete_login')


class OauthProvider:
    provider = None

    def __init__(self):
        if OauthProvider.provider is None:
            OauthProvider.provider = OAuth2Service(
                client_id=current_app.config['FACEBOOK_CONSUMER_KEY'],
                client_secret=current_app.config['FACEBOOK_CONSUMER_SECRET'],
                name='facebook',
                authorize_url='https://www.facebook.com/v14.0/dialog/oauth',
                access_token_url='https://graph.facebook.com/v14.0/oauth/access_token',
                base_url='https://graph.facebook.com/'
            )
        self.provider = OauthProvider.provider


@auth_bp.route("/register", methods=["POST"])
async def register():
    form_data = await request.form
    data = form_data.to_dict()
    form = RegistrationForm(form_data)
    if form.validate():
        data['password'] = generate_password_hash(data['password'])
        # TODO :: Validate X-Forwarded-For header before go production
        try:
            geolocation_data = requests.get(
                f"http://ip-api.com/json/{request.headers.get('X-Forwarded-For')}").json()
            data['country'] = geolocation_data['country']
        except Exception as e:
            data['country'] = ''

        data.pop('confirm')
        await db.register_user(data)
        return jsonify({
            'message': 'registered.'
        }), 201

    return jsonify({
        "message": form.errors
    }), 400


@auth_bp.route("/login", methods=["POST"])
async def login():
    form_data = await request.form
    form = LoginForm(form_data)
    if form.validate():
        data = form_data.to_dict()
        user = await db.find_user(data['email'], {"_id": 1, "email": 1, "username": 1, "password": 1})
        if not check_password_hash(user['password'], data['password']):
            return jsonify({
                "message": f"Username or Password in correct. TRY AGAIN."
            }), 202
        access_token = create_access_token(
            identity=user['email'],
            additional_claims= {'user_id':str(user['_id']),'user_name':user['username']}
        )
        refresh_token = create_refresh_token(
            identity=user['email'],
            additional_claims={'user_id':str(user['_id']),'user_name':user['username']}
        )
        insert_result = await db.create_login_session(refresh_token, user['email'], user['_id'])

        return await make_response(jsonify({
            'auth_token': access_token,
            'refresh_token': refresh_token
        }), 200)

    return jsonify({
        "message": form.errors
    }), 400



@auth_bp.route("/logout", methods=["POST"])
@jwt_required()
async def logout():
    acces_token = get_jwt()
    form = await request.form
    refresh_token = form.get('refresh_token', None)
    if await db.logout_user(refresh_token):
        return jsonify({"status": "success"}), 200




@auth_bp.route("/refresh", methods=['POST'])
@jwt_required(refresh=True)
async def refresh():
    refresh_token = get_jwt()
    try:
        await db.find_refresh_token(refresh_token)
    except DbError as e:
        return jsonify({"message": 'Please login again.'}), 202

    identity = refresh_token['sub']
    access_token = create_access_token(
            identity=identity,
            additional_claims= {'user_id':refresh_token['user_id'],'user_name':refresh_token['user_name']}
        )
    return jsonify({'auth_token': access_token}), 200


@oauth_bp.route('/', methods=['GET'])
async def redirect_authorization():
    facebook = OauthProvider().provider
    return redirect(
        facebook.get_authorize_url(redirect_uri=url_for("oauth.authorize", _scheme='https'),scope='email')
    )


@oauth_bp.route("/Authorize", methods=['GET'])
async def authorize():

    facebook = OauthProvider().provider

    def decode_json(payload):
        return json.loads(payload.decode('utf-8'))
    if "code" not in request.args:
        """"
        This code block will run if user decline Login dialog.
        YOUR_REDIRECT_URI?
        error_reason=user_denied
        &error=access_denied
        &error_description=Permissions+error.
        """
        return redirect('/')
    oauth_session = facebook.get_auth_session(
        data={'code': request.args['code'],
              'redirect_uri': url_for("oauth.authorize", _scheme='https')},
        decoder=decode_json
    )
    me = oauth_session.get('me', params={'fields': 'email'}).json()

    user = await db.db.users.find_one({'email':me['email']},{"_id": 1, "email": 1,'username':1})
    if user:
        # User already registered so just login user
        access_token = create_access_token(
            identity=user['email'],
            additional_claims= {'user_id':str(user['_id']),'user_name':user['username']}
        )
        refresh_token = create_refresh_token(
            identity=user['email'],
            additional_claims={'user_id':str(user['_id']),'user_name':user['username']}
        )
        result = await db.create_login_session(refresh_token, user['email'], user['_id'])
        return redirect("https://" + current_app.config['SERVER_NAME'] + f"/static/token.html?auth_token={access_token}&refresh_token={refresh_token}")
    else:
        # User not registered before register and login user
        me.pop('id')
        register_result = await db.register_user(me)
        access_token = create_access_token(identity=me['email'])
        refresh_token = create_refresh_token(identity=me['email'])
        return redirect("https://" + current_app.config['SERVER_NAME'] + f"/static/token.html?auth_token={access_token}&refresh_token={refresh_token}")


@oauth_bp.route('/complete',methods=['POST'])
@jwt_required()
async def complete():
    #data = {
    #    'avatar':int,
    #    'username':str,
    #    'country':None
    #}
    token = get_jwt()
    form_data = await request.form
    data = form_data.to_dict()
    form = CompleteLoginForm(form_data)
    if form.validate():

        try:
            geolocation_data = requests.get(
                f"http://ip-api.com/json/{request.headers.get('X-Forwarded-For')}").json()
            data['country'] = geolocation_data['country']
        except Exception as e:
            data['country'] = ''

        await db.complete_login(data,token['sub'])
        user = await db.db.users.find_one({'email':token['sub']})

        access_token = create_access_token(
            identity=user['email'],
            additional_claims={'user_id': str(user['_id']), 'user_name': data['username']}
        )
        refresh_token = create_refresh_token(
            identity=user['email'],
            additional_claims={'user_id': str(user['_id']), 'user_name': data['username']}
        )

        result = await db.create_login_session(refresh_token, user['email'], user['_id'])

        return await make_response(jsonify({
            'auth_token': access_token,
            'refresh_token': refresh_token
        }), 200)

    return jsonify({
        "message": form.errors
    }), 400