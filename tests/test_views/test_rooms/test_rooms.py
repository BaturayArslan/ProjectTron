import asyncio

import pytest
import pytest_asyncio
from bson import ObjectId
from quart_jwt_extended import decode_token
from werkzeug.local import LocalProxy
import json
import base64
import weakref
from quart import g, current_app

from projectTron import db
from projectTron import redis
from projectTron import factory
from projectTron.utils.utils import objectid_to_str


@pytest_asyncio.fixture(scope='class')
async def register_users(class_client, class_app):
    """
        This fixture drop existing users collection and recreate that collection and register two user 'user1' and 'user2'
    """
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
async def get_login_info_fixture(class_client, class_app):
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
async def get_room_info_fixture(class_client, class_app, get_login_info_fixture):
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
        user1, user2 = get_login_info_fixture
        data = {
            "name":"test_room",
            "max_user": 4,
            "max_point": 15,
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
        return result_json['message']['room_id']


@pytest.mark.asyncio
@pytest.mark.usefixtures("login_user_fixture")
class TestCreateRoom:

    async def test_create_room(self, class_client, class_app, get_login_info_fixture):
        client = class_client
        app = class_app
        async with app.app_context():
            # Get reddis connections for test events
            pubsub, redis_connection = await redis.get_redis()
            user1, user2 = get_login_info_fixture
            # Decode auth_token
            acces_token_header, acces_token_paylaod, acces_token_signature = user1['auth_token'].split('.')
            user1_token = json.loads(base64.b64decode(acces_token_paylaod + "=="))
            db_instance = db.db
            data = {
                "name": "test_room",
                "max_user": 4,
                "max_point": 15,
                'password': ''
            }
            headers = {
                'Authorization': f'Bearer {user1["auth_token"]}'
            }
            task = asyncio.create_task(client.post('/room/createRoom', form=data, headers=headers))
            event = await redis.broker.subscribe()
            result = await task
            result_json = await result.get_json()
            assert result.status_code == 201
            message = result_json['message']
            room = await db_instance.rooms.find_one({'_id': ObjectId(message['room_id'])})
            assert room != None
            assert room['max_user'] == data['max_user']
            assert room['status'] == {'public': True, 'password': '',"current_round":0,"is_start":False}
            assert room['admin'] == ObjectId(user1_token["user_claims"]['user_id'])

            # Check if correct event published or not.
            room['status'].pop('password')
            assert event['data'] == objectid_to_str(room)

    async def test_user_already_in_room(self, class_client, class_app, get_login_info_fixture, get_room_info_fixture):
        client = class_client
        app = class_app
        async with app.app_context():
            db_instance = db.db
            user1, user2 = get_login_info_fixture
            room_id = get_room_info_fixture
            user2_token = decode_token(user2['auth_token'])
            data = {
                "name": "test_room",
                "max_user": 4,
                "max_point": 15,
                'password': ''
            }
            headers = {
                'Authorization': f'Bearer {user2["auth_token"]}'
            }
            join_data = {
                'password': ''
            }
            await client.post(f'/room/{room_id}', form=join_data, headers=headers)
            result = await client.post('/room/createRoom', form=data, headers=headers)
            result_json = await result.get_json()
            assert result.status_code == 200
            assert result_json['message'] == 'You Already in a another room.'

    # Todo test a data erro occur when user try to join new created room
    # async def test_UserJoinRoomFailed_error(self, class_client, class_app, get_login_info_fixture, get_room_info_fixture):
    #     async with app.app_context():
    #         user1, user2 = get_login_info_fixture
    #         room_id = get_room_info_fixture
    #         user1_token = decode_token(user1['auth_token'])


@pytest.mark.asyncio
@pytest.mark.usefixtures("login_user_fixture")
class TestJoinRoom:
    async def test_join_room(self, class_client, class_app, get_login_info_fixture, get_room_info_fixture):
        app = class_app
        client = class_client
        async with app.app_context():
            user1, user2 = get_login_info_fixture
            room_id = get_room_info_fixture
            user1_token = decode_token(user1['auth_token'])

            pubsub, redis_connection = await redis.get_redis()
            db_instance = db.db

            headers = {
                'Authorization': f'Bearer {user1["auth_token"]}'
            }

            data = {
                'password': ''
            }

            task = asyncio.create_task(client.post(f'/room/{room_id}', form=data, headers=headers))
            event = await redis.broker.subscribe()
            result = await task
            result_json = await result.get_json()
            assert result.status_code == 200
            assert result_json['message'] == 'OK'
            assert event['name'] == 'user join'
            assert event['room_id'] == room_id

@pytest.mark.asyncio
@pytest.mark.usefixtures('login_user_fixture')
class TestLeaveRoom:
    async def test_leave_room(self,class_client,class_app,get_login_info_fixture,get_room_info_fixture):
        app = class_app
        client = class_client
        async with app.app_context():
            user1,user2  =get_login_info_fixture
            pubsub,redis_connection = await redis.get_redis()
            room_id = get_room_info_fixture

            headers = {
                'Authorization': f'Bearer {user2["auth_token"]}'
            }
            join_data = {
                'password': ''
            }
            # request for join room.
            await client.post(f'/room/{room_id}', form=join_data, headers=headers)
            # request for leave room.
            task = asyncio.create_task(client.get(f'/room/leaveRoom/{room_id}', headers=headers))
            # one for user join event
            event = await redis.broker.subscribe()
            #one for user leave event
            event = await redis.broker.subscribe()
            result = await task
            result_json = await result.get_json()
            assert result.status_code == 200
            assert result_json['message'] == 'OK'
            assert event['name'] == 'user leaves'
            assert event['room_id'] == room_id

@pytest.mark.asyncio
@pytest.mark.usefixtures('login_user_fixture')
class TestRefreshRoomsInfo:
    async def test_refresh_rooms_info(self, class_client, class_app, get_login_info_fixture,get_room_info_fixture):
        app = class_app
        client = class_client
        async with app.app_context():
            user1, user2 = get_login_info_fixture
            room_id = get_room_info_fixture
            pubsub, redis_connection = await redis.get_redis()
            headers = {
                'Authorization': f'Bearer {user1["auth_token"]}'
            }
            data = {
                'password':''
            }
            # this connection can hold up to 120 second
            task1 = asyncio.create_task(client.get("/room/update", headers=headers))
            await asyncio.sleep(3)
            join_room_result = await client.post(f'/room/{room_id}', form=data, headers=headers)
            join_room_result_json = await join_room_result.get_json()
            result = await task1
            result_json = await result.get_json()
            assert result.status_code == 200
            assert join_room_result.status_code == 200
            assert result_json['message']['room_id'] == room_id
            assert result_json['message']['name'] == 'user join'

            event = result_json['message']

            # Miss one event so we expect from server to serve missed event and syncronize us.
            leave_room_result = await client.get(f'/room/leaveRoom/{room_id}', headers=headers)
            assert leave_room_result.status_code == 200

            params = {
                'timestamp': event['timestamp']
            }

            join_room_result = await client.post(f'/room/{room_id}', form=data, headers=headers)
            task1 = asyncio.create_task(client.get("/room/update", headers=headers,query_string=params))
            join_room_result_json = await join_room_result.get_json()
            result = await task1
            result_json = await result.get_json()
            assert len(result_json['events']) == 2