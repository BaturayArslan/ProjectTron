import pytest
import pytest_asyncio
import asyncio

from drawProject import db,redis

from drawProject import factory
@pytest_asyncio.fixture(scope='class')
async def register_users(class_app,class_client):
    """
        This fixture drop existing users collection and recreate that collection and register two user 'user1' and 'user2'
    """
    # Trigger app.before_first_request function
    await class_client.get('/')

    async with class_app.app_context():
        db_instance = db.db
        await db_instance.drop_collection('users')
        await db_instance.create_collection('users')
        await db_instance.users.create_index('email', unique=True)
        user1 = {
            "email": "user1@user1.com",
            "username": "user1",
            "password": "user1password",
            "avatar": 1,
            "confirm": "user1password",
        }
        user2 = {
            "email": "user2@user2.com",
            "username": "user2",
            "password": "user2password",
            "avatar": 1,
            "confirm": "user2password",
        }
        result1 = await class_client.post('/auth/register', form=user1)
        result2 = await class_client.post('/auth/register', form=user2)
        assert result1.status_code == 201
        assert result2.status_code == 201

@pytest_asyncio.fixture(scope='class')
async def login_user_fixture(class_client, class_app, register_users):
    async with class_app.app_context():
        db_instance = db.db
        await db_instance.drop_collection('sessions')
        await db_instance.create_collection('sessions')
        await db_instance.sessions.create_index('jti', unique=True)

@pytest_asyncio.fixture()
async def get_user(class_client, class_app):
    """
        This fixture login 'user1' and 'user2' that registered with register_user_fixture
        and returns:
            {
                'status':'success',
                'auth_token':str
                'refresh_token':str
            }
    """
    app = class_app
    client = class_client
    async with app.app_context():
        user1 = {
            'email': 'user1@user1.com',
            'password': 'user1password'
        }
        user2 = {
            'email': 'user2@user2.com',
            'password': 'user2password'
        }

        user1_login_response = await client.post('/auth/login', form=user1)
        user2_login_response = await client.post('/auth/login', form=user2)
        user1_login_info = await user1_login_response.get_json()
        user2_login_info = await user2_login_response.get_json()
        assert user1_login_response.status_code == 200
        assert user2_login_response.status_code == 200
        return user1_login_info, user2_login_info

@pytest_asyncio.fixture()
async def get_room(class_client, class_app, get_user):
    """
        This fixture drop existing rooms and recreate rooms collection and Create new room with 'user2' user
        returns room_id
    """
    app = class_app
    client = class_client

    async with app.app_context():
        db_instance = db.db
        await redis.get_redis()
        await db_instance.drop_collection('rooms')
        await db_instance.create_collection('rooms')
        user1, user2 = get_user
        data = {
            "max_user": 4,
            "max_point": 100,
            'password': ''
        }
        headers = {
            'Authorization': f'Bearer {user2["auth_token"]}'
        }
        task = asyncio.create_task(client.post('/room/createRoom', form=data, headers=headers))
        await redis.broker.subscribe()
        result = await task
        result_json = await result.get_json()
        assert result.status_code == 201
        assert result_json['status'] == "success"
        return result_json['message']['room_id']