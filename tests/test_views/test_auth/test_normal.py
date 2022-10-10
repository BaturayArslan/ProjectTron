from projectTron import db
import pytest
import base64
import json
import jwt
import pytest_asyncio
from datetime import datetime
from quart import g, current_app


@pytest_asyncio.fixture(scope="class")
async def register_fixture(class_app,class_client):
    """
        Drop Already Exist users collection and create refresh one
    """
    # Trigger app.before_first_request function
    await class_client.get('/')

    db_instance = db.db
    async with class_app.app_context():
        await db_instance.drop_collection('users')
        await db_instance.create_collection('users')
        await db_instance.users.create_index('email', unique=True)


@pytest_asyncio.fixture
async def login_response(class_client, class_app):
    client = class_client
    app = class_app

    data = {
        'email': 'test@test.com',
        'password': 'testpassword'
    }
    login_response = await client.post("/auth/login", form=data)
    login_response_json = await login_response.get_json()
    assert login_response.status_code == 200
    assert "auth_token" in login_response_json
    assert "refresh_token" in login_response_json
    return login_response, login_response_json


@pytest_asyncio.fixture(scope="class")
async def login_fixture(class_app, class_client):
    await class_client.get('/')
    db_instance = db.db
    async with class_app.app_context():
        await db_instance.drop_collection('users')
        await db_instance.create_collection('users')
        await db_instance.users.create_index("emial", unique=True)
        data = {
            "email": "test@test.com",
            "username": "test",
            "password": "testpassword",
            "avatar": 1,
            "confirm": "testpassword",
        }
        await class_client.post("/auth/register", form=data)
        await db_instance.drop_collection('sessions')
        await db_instance.create_collection('sessions')
        await db_instance.sessions.create_index('jti', unique=True)

@pytest.mark.asyncio
@pytest.mark.usefixtures('register_fixture')
class TestRegister:

    @pytest.mark.parametrize("data,headers,path,expected", [
        (
                {
                    "email": "test@test.com",
                    "username": "test",
                    "password": "test",
                    "avatar": 1,
                    "confirm": "test",
                },
                {
                    "X-Forwarded-For": '94.123.218.184'
                },
                "/auth/register",
                {
                    "status_code": 201,
                    "status": "success",
                    'message': 'registered.'
                }

        ),
        (
                {
                    "email": "test@test.com",
                    "username": "test",
                    "password": "test",
                    "avatar": 1,
                    "confirm": "test",
                    "hello": "world"
                },
                {
                    "X-Forwarded-For": '94.123.218.184'
                },
                "/auth/register",
                {
                    "status_code": 202,
                    "status": "error",
                    'message': 'This email already registered.Please try another email.'
                }

        ),
        (
                {
                    "email": "test2@test.com",
                    "username": "test",
                    "password": "test",
                    "avatar": 3,
                    "confirm": "test",
                },
                None,
                "/auth/register",
                {
                    "status_code": 201,
                    "status": "success",
                    'message': 'registered.'
                }

        ),
        (
                {
                    "email": "test",
                    "username": "t",
                    "password": "dwdasdasd",
                    "avatar": "huuu",
                    "confirm": "test"
                },
                None,
                "/auth/register",
                {
                    "status_code": 400,
                    "status": "error",
                    "message": {
                        "password": ["Passwords must match."],
                        "email": ["Email must be valid."],
                        "username": ["min must be 2,max must be 25"],
                        "avatar": ["Please enter avatar value"],
                    }

                }

        )
    ])
    async def test_register(self, class_client, data, headers, path, expected):
        client = class_client

        response = await client.post(path, form=data, headers=headers)
        response_json = await response.get_json()
        data = await response.data
        assert response.status_code == expected['status_code']
        assert response_json['message'] == expected['message']




@pytest.mark.usefixtures("login_fixture")
@pytest.mark.asyncio
class TestLogin:
    async def test_succesfull_login(self, class_client, class_app):
        client = class_client
        app = class_app
        data = {
            'email': 'test@test.com',
            'password': 'testpassword'
        }
        response = await client.post("/auth/login", form=data)
        response_json = await response.get_json()
        assert response.status_code == 200
        access_header, access_claims, access_sign = response_json['auth_token'].split(".")
        decoded_access_claims = json.loads(base64.b64decode(access_claims + "=="))
        assert decoded_access_claims['sub'] == "test@test.com"
        assert decoded_access_claims['type'] == "access"
        exp_date = datetime.fromtimestamp(decoded_access_claims['exp'])
        issued_date = datetime.fromtimestamp(decoded_access_claims['iat'])
        assert str(exp_date - issued_date) == f"{str(app.config['JWT_ACCESS_TOKEN_EXPIRES'])}"

        refresh_header, refresh_claims, refresh_sign = response_json['refresh_token'].split(".")
        decoded_refresh_claims = json.loads(base64.b64decode(refresh_claims + "=="))
        assert decoded_refresh_claims['sub'] == "test@test.com"
        assert decoded_refresh_claims['type'] == "refresh"
        exp_date = datetime.fromtimestamp(decoded_refresh_claims['exp'])
        issued_date = datetime.fromtimestamp(decoded_refresh_claims['iat'])
        assert str(exp_date - issued_date) == f"{str(app.config['JWT_REFRESH_TOKEN_EXPIRES'])}"

    async def test_invalid_credentials_login(self, class_client, class_app):
        client = class_client
        app = class_app
        data = {
            'email': 'test@test.com',
            'password': 'invalidpassword'
        }
        response = await client.post("/auth/login", form=data)
        response_json = await response.get_json()
        assert response.status_code == 202
        assert response_json['message'] == "Username or Password in correct. TRY AGAIN."


@pytest.mark.usefixtures("login_fixture")
@pytest.mark.asyncio
class TestLogout:
    async def test_logout(self, class_client, class_app):
        client = class_client
        app = class_app

        data = {
            'email': 'test@test.com',
            'password': 'testpassword'
        }
        login_response = await client.post("/auth/login", form=data)
        login_response_json = await login_response.get_json()
        assert login_response.status_code == 200
        assert "auth_token" in login_response_json
        assert "refresh_token" in login_response_json

        headers = {
            "Authorization": f"Bearer {login_response_json['auth_token']}"
        }
        logout_data = {
            "refresh_token": f"{login_response_json['refresh_token']}"
        }
        response = await client.post("/auth/logout", headers=headers, form=logout_data)
        response_json = await response.get_json()
        assert response.status_code == 200

    async def test_logout_without_access_token(self, class_client, class_app, login_response):
        client = class_client
        app = class_app

        _login_response, _login_response_json = login_response
        data = {
            "refresh_token": _login_response_json['refresh_token']
        }
        response = await client.post("/auth/logout", form=data)
        response_json = await response.get_json()
        assert response.status_code == 402
        assert response_json['message'] == "Missing Token."

    async def test_logout_without_refresh_token(self, class_client, class_app, login_response):
        client = class_client
        app = class_app

        _login_response, _login_response_json = login_response

        headers = {
            "Authorization": f"Bearer {_login_response_json['auth_token']}"
        }
        response = await client.post("/auth/logout", headers=headers)
        response_json = await response.get_json()
        assert response.status_code == 400
        assert response_json['message'] == "Missing refresh token."


@pytest.mark.usefixtures("login_fixture")
@pytest.mark.asyncio
class TestRefreshToken:
    async def test_refresh_token(self, class_client, class_app,login_response):
        client = class_client
        app = class_app

        _login_response, _login_response_json = login_response

        headers = {
            "Authorization": f"Bearer {_login_response_json['refresh_token']}"
        }

        response = await client.post("/auth/refresh", headers=headers)
        response_json = await response.get_json()
        assert response.status_code == 200
        access_header, access_claims, access_sign = response_json['auth_token'].split(".")
        decoded_access_claims = json.loads(base64.b64decode(access_claims + "="))
        assert decoded_access_claims['sub'] == "test@test.com"
        assert decoded_access_claims['type'] == "access"
        exp_date = datetime.fromtimestamp(decoded_access_claims['exp'])
        issued_date = datetime.fromtimestamp(decoded_access_claims['iat'])
        assert str(exp_date - issued_date) == f"{str(app.config['JWT_ACCESS_TOKEN_EXPIRES'])}"

    async def test_invalid_refresh_token(self, class_client, class_app):
        client = class_client
        app = class_app

        payload = {
            "sub": "test@test.com",

        }
        fake_token = jwt.decode(payload, "fake token")
        headers = {
            "Authorization": f"Bearer {fake_token}"
        }
        response = client.post("/auth/refresh", headers=headers)
        response_json = response.get_json()
        # Invalid signature

        # expired token
