import asyncio

import pytest
import pytest_asyncio
from bson import ObjectId
from flask_jwt_extended import decode_token
from werkzeug.local import LocalProxy
import json
import base64
import weakref
from quart import g,current_app

from drawProject import db
from drawProject import redis
from drawProject import factory

@pytest_asyncio.fixture(scope='class')
async def register_users(class_client, class_app):
    """
        This fixture drop existing users collection and recreate that collection and register two user 'user1' and 'user2'
    """
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
async def get_login_info_fixture(client, app):
    """
        This fixture login 'user1' and 'user2' that registered with register_user_fixture
        and returns:
            {
                'status':'success',
                'auth_token':str
                'refresh_token':str
            }
    """
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
async def get_room_info_fixture(client, app, get_login_info_fixture):
    """
        This fixture drop existing rooms and recreate rooms collection and Create new room with 'user2' user
        returns room_id
    """
    async with app.app_context():
        db_instance = db.db
        await db_instance.drop_collection('rooms')
        await db_instance.create_collection('rooms')
        user1, user2 = get_login_info_fixture
        data = {
            "max_user": 4,
            "max_point": 100,
            'password': ''
        }
        headers = {
            'Authorization': f'Bearer {user2["auth_token"]}'
        }
        result = await client.post('/room/createRoom', form=data, headers=headers)
        result_json = await result.get_json()
        assert result.status_code == 201
        assert result_json['status'] == "success"
        return result_json['message']['room_id']


@pytest.mark.asyncio
@pytest.mark.usefixtures("login_user_fixture")
class TestCreateRoom:

    async def test_create_room(self, get_login_info_fixture):
        app = factory.create_app(test=True)
        client = app.test_client()
        async with app.app_context():
            pubsub,redis_connection = await redis.get_redis()
            user1, user2 = get_login_info_fixture
            #Decode auth_token
            acces_token_header, acces_token_paylaod, acces_token_signature = user1['auth_token'].split('.')
            user1_token = json.loads(base64.b64decode(acces_token_paylaod + "="))
            #Get reddis connections for test events
            db_instance = db.db
            data = {
                "max_user": 4,
                "max_point": 100,
                'password': ''
            }
            headers = {
                'Authorization': f'Bearer {user1["auth_token"]}'
            }
            print('5')
            result = await client.post('/room/createRoom', form=data, headers=headers)
            print('6')
            result_json = await result.get_json()
            assert result.status_code == 201
            assert result_json['status'] == 'success'
            message = result_json['message']
            room = await db_instance.rooms.find_one({'_id': ObjectId(message['room_id'])})
            assert room != None
            assert room['max_user'] == data['max_user']
            assert room['status'] == {'public': True, 'password': ''}
            assert room['admin'] == ObjectId(user1_token['user_id'])
            assert {'_id': ObjectId(ObjectId(user1_token['user_id'])), 'point': 0, "color": 0, 'win_count': 0,
                    'kick_vote': 0, } in room['users']
            #Check if correct event published or not.
            # while True:
            #     message = await pubsub.get_message(ignore_subscribe_messages=True)
            #     if message:
            #         event = json.loads(message['data'])
            #         break
            event = await redis.broker.subscribe()
            print(event)
    async def test_user_already_in_room(self, client, app, get_login_info_fixture, get_room_info_fixture):
        async with app.app_context():
            db_instance = db.db
            user1, user2 = get_login_info_fixture
            room_id = get_room_info_fixture
            user2_token = decode_token(user2['auth_token'])
            data = {
                "max_user": 4,
                "max_point": 100,
                'password': ''
            }
            headers = {
                'Authorization': f'Bearer {user2["auth_token"]}'
            }
            result = await client.post('/room/createRoom', form=data, headers=headers)
            result_json = await result.get_json()
            assert result.status_code == 500
            assert result_json['status'] == 'error'
            assert result_json['message'] == 'You Already in a room.'

    # Todo test a data erro occur when user try to join new created room
    async def test_UserJoinRoomFailed_error(self, client, app, get_login_info_fixture, get_room_info_fixture):
        async with app.app_context():
            user1, user2 = get_login_info_fixture
            room_id = get_room_info_fixture
            user1_token = decode_token(user1['auth_token'])


@pytest.mark.asyncio
@pytest.mark.usefixtures("login_user_fixture")
class TestJoinRoom:
    async def test_join_room(self, client, app, get_login_info_fixture, get_room_info_fixture):
        async with app.app_context():
            user1, user2 = get_login_info_fixture
            room_id = get_room_info_fixture
            user1_token = decode_token(user1['auth_token'])

            headers = {
                'Authorization': f'Bearer {user1["auth_token"]}'
            }

            data = {
                'password': ''
            }

            result = await client.post(f'/room/{room_id}', form=data, headers=headers)
            result_json = await result.get_json()
            assert result.status_code == 200
            assert result_json['status'] == 'success'
            assert result_json['message'] == 'OK'


@pytest.mark.asyncio
@pytest.mark.usefixtures('login_user_fixture')
class TestRefreshRoomsInfo:
    async def test_refresh_rooms_info(self,client,app,get_login_info_fixture):
        async with app.app_context():
            user1, user2 = get_login_info_fixture
            pubsub , redis_connection = await redis.get_redis()
            message = {
                'data':'some random data.'
            }
            headers = {
                'Authorization': f'Bearer {user1["auth_token"]}'
            }
            # this connection can hold up to 120 second
            task1 =  asyncio.create_task(client.get("/room/update",headers=headers))
            await asyncio.sleep(5)
            await redis_connection.publish('rooms_info_feed',json.dumps(message))
            result = await task1
            result_json = result.get_json()
            print(result_json)
