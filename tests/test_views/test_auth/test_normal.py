from drawProject import db
import pytest
import base64
import json
import jwt
from datetime import datetime
from flask import g, current_app


@pytest.fixture(scope="class")
def register_fixture(class_app):
    """
        Drop Already Exist users collection and create refresh one
    """
    db_instance = db.db
    with class_app.app_context():
        db_instance.drop_collection('users')
        db_instance.create_collection('users')
        db_instance.users.create_index('email', unique=True)


@pytest.fixture
def login_response(client, app):
    data = {
        'email': 'test@test.com',
        'password': 'testpassword'
    }
    login_response = client.post("/auth/login", data=data)
    login_response_json = login_response.get_json()
    assert login_response.status_code == 200
    assert login_response_json['status'] == "success"
    assert "auth_token" in login_response_json
    assert "refresh_token" in login_response_json
    return login_response, login_response_json


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
    def test_register(self, client, data, headers, path, expected):
        response = client.post(path, data=data, headers=headers)
        response_json = response.get_json()
        assert response.status_code == expected['status_code']
        assert response_json['status'] == expected['status']
        assert response_json['message'] == expected['message']


@pytest.fixture(scope="class")
def login_fixture(class_app, class_client):
    db_instance = db.db
    with class_app.app_context():
        db_instance.drop_collection('users')
        db_instance.create_collection('users')
        db_instance.users.create_index("emial", unique=True)
        data = {
            "email": "test@test.com",
            "username": "test",
            "password": "testpassword",
            "avatar": 1,
            "confirm": "testpassword",
        }
        class_client.post("/auth/register", data=data)
        db_instance.drop_collection('sessions')
        db_instance.create_collection('sessions')
        db_instance.sessions.create_index('jti', unique=True)


@pytest.mark.usefixtures("login_fixture")
class TestLogin:
    def test_succesfull_login(self, client, app):
        data = {
            'email': 'test@test.com',
            'password': 'testpassword'
        }
        response = client.post("/auth/login", data=data)
        response_json = response.get_json()
        assert response.status_code == 200
        assert response_json['status'] == "success"
        access_header, access_claims, access_sign = response_json['auth_token'].split(".")
        decoded_access_claims = json.loads(base64.b64decode(access_claims + "="))
        assert decoded_access_claims['sub'] == "test@test.com"
        assert decoded_access_claims['type'] == "access"
        exp_date = datetime.fromtimestamp(decoded_access_claims['exp'])
        issued_date = datetime.fromtimestamp(decoded_access_claims['iat'])
        assert str(exp_date - issued_date) == f"{str(app.config['JWT_ACCESS_TOKEN_EXPIRES'])}"

        refresh_header, refresh_claims, refresh_sign = response_json['refresh_token'].split(".")
        decoded_refresh_claims = json.loads(base64.b64decode(refresh_claims + "="))
        assert decoded_refresh_claims['sub'] == "test@test.com"
        assert decoded_refresh_claims['type'] == "refresh"
        exp_date = datetime.fromtimestamp(decoded_refresh_claims['exp'])
        issued_date = datetime.fromtimestamp(decoded_refresh_claims['iat'])
        assert str(exp_date - issued_date) == f"{str(app.config['JWT_REFRESH_TOKEN_EXPIRES'])}"

    def test_invalid_credentials_login(self, client, app):
        data = {
            'email': 'test@test.com',
            'password': 'invalidpassword'
        }
        response = client.post("/auth/login", data=data)
        response_json = response.get_json()
        assert response.status_code == 202
        assert response_json['status'] == "error"
        assert response_json['message'] == "Username or Password in correct. TRY AGAIN."


@pytest.mark.usefixtures("login_fixture")
class TestLogout:
    def test_logout(self, client, app):
        data = {
            'email': 'test@test.com',
            'password': 'testpassword'
        }
        login_response = client.post("/auth/login", data=data)
        login_response_json = login_response.get_json()
        assert login_response.status_code == 200
        assert login_response_json['status'] == "success"
        assert "auth_token" in login_response_json
        assert "refresh_token" in login_response_json

        headers = {
            "Authorization": f"Bearer {login_response_json['auth_token']}"
        }
        logout_data = {
            "refresh_token": f"{login_response_json['refresh_token']}"
        }
        response = client.post("/auth/logout", headers=headers, data=logout_data)
        response_json = response.get_json()
        assert response.status_code == 200
        assert response_json['status'] == "success"

    def test_logout_without_access_token(self, client, app, login_response):
        _login_response, _login_response_json = login_response
        data = {
            "refresh_token": _login_response_json['refresh_token']
        }
        response = client.post("/auth/logout", data=data)
        response_json = response.get_json()
        assert response.status_code == 402
        assert response_json['status'] == "error"
        assert response_json['message'] == "Missing Token."

    def test_logout_without_refresh_token(self, client, app, login_response):
        _login_response, _login_response_json = login_response

        headers = {
            "Authorization": f"Bearer {_login_response_json['auth_token']}"
        }
        response = client.post("/auth/logout", headers=headers)
        response_json = response.get_json()
        assert response.status_code == 400
        assert response_json['status'] == "error"
        assert response_json['message'] == "Missing refresh token."


@pytest.mark.usefixtures("login_fixture")
class TestRefreshToken:
    def test_refresh_token(self, client, app,login_response):
        _login_response, _login_response_json = login_response

        headers = {
            "Authorization": f"Bearer {_login_response_json['refresh_token']}"
        }

        response = client.post("/auth/refresh", headers=headers)
        response_json = response.get_json()
        assert response.status_code == 200
        assert response_json['status'] == "success"
        access_header, access_claims, access_sign = response_json['auth_token'].split(".")
        decoded_access_claims = json.loads(base64.b64decode(access_claims))
        assert decoded_access_claims['sub'] == "test@test.com"
        assert decoded_access_claims['type'] == "access"
        exp_date = datetime.fromtimestamp(decoded_access_claims['exp'])
        issued_date = datetime.fromtimestamp(decoded_access_claims['iat'])
        assert str(exp_date - issued_date) == f"{str(app.config['JWT_ACCESS_TOKEN_EXPIRES'])}"

    def test_invalid_refresh_token(self, client, app):
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
