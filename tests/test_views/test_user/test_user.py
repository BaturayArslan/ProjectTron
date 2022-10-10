import pytest
import pytest_asyncio
from flask_jwt_extended import decode_token

from projectTron import db
from projectTron import redis
from projectTron.utils import utils

@pytest_asyncio.fixture(scope='class')
async def register_users(class_app,class_client):
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

@pytest.mark.usefixtures('login_user_fixture')
@pytest.mark.asyncio
class TestSendMessage:
    async def test_send_message(self,class_app,class_client,get_user):
        app = class_app
        client = class_client
        async with app.app_context():
            user1,user2 = get_user
            user1_token = decode_token(user1["auth_token"].encode('utf-8'))
            user2_token = decode_token(user2["auth_token"].encode('utf-8'))
            pubsub, redis_connection = await redis.get_redis()

            headers = {
                'Authorization' : f'Bearer {user1["auth_token"]}'
            }
            headers2 = {
                'Authorization' : f'Bearer {user2["auth_token"]}'
            }
            message={
                'friend_id': user2_token['user_id'],
                'msg': 'merhaba'
            }
            params={
                'friend_id': user2_token['user_id'],
                'avatar': 1
            }
            params2={
                'friend_id': user1_token['user_id'],
                'avatar': 1
            }

            add_result = await client.get('/user/add_friend', headers=headers, query_string=params)
            assert add_result.status_code == 200

            add_result2 = await client.get('/user/add_friend', headers=headers2, query_string=params2)
            assert add_result2.status_code == 200

            result = await client.post('/user/send_message',json=message,headers=headers)
            result_json = await result.get_json()
            assert result.status_code == 200
            assert result_json['message']['msg'] == 'merhaba'
            assert result_json['message']['sender'] == user1_token['user_id']
            assert result_json['message']['reciever'] == user2_token['user_id']
            redis_timestamp = utils.normal_to_redis_timestamp(result_json['message']['timestamp'])
            stream_event = await redis_connection.xread({user2_token['user_id']:0},count=1)
            event = stream_event[0][1][0][1]
            assert float(event['timestamp'.encode('utf-8')].decode('utf-8')) == result_json['message']['timestamp']

@pytest.mark.usefixtures('login_user_fixture')
@pytest.mark.asyncio
class TestAddFriend:
    async def test_add_friend(self,class_app,class_client,get_user):
        client = class_client
        app = class_app
        async with app.app_context():
            user1,user2 = get_user
            user1_token = decode_token(user1["auth_token"].encode('utf-8'))
            user2_token = decode_token(user2["auth_token"].encode('utf-8'))

            headers = {
                'Authorization' : f'Bearer {user1["auth_token"]}'
            }
            params={
                'friend_id': user2_token['user_id'],
                'avatar': 1
            }


            result = await client.get('/user/add_friend',headers=headers,query_string=params)
            result_json = await result.get_json()
            assert result.status_code == 200
            assert result_json['status'] == 'success'
            assert result_json['message']['friends'][0]['_id'] == user2_token['user_id']


@pytest.mark.usefixtures('login_user_fixture')
@pytest.mark.asyncio
class TestDeleteFriend:
    async def test_delete_friend(self,class_app,class_client,get_user):
        client = class_client
        app = class_app
        async with app.app_context():
            user1,user2 = get_user
            user1_token = decode_token(user1["auth_token"].encode('utf-8'))
            user2_token = decode_token(user2["auth_token"].encode('utf-8'))

            headers = {
                'Authorization' : f'Bearer {user1["auth_token"]}'
            }
            add_params={
                'friend_id': user2_token['user_id'],
                'avatar': 1
            }
            delete_params= {
                'friend_id': user2_token['user_id'],
            }

            add_result = await client.get('/user/add_friend', headers=headers, query_string=add_params)
            assert add_result.status_code == 200

            result = await client.get('/user/delete_friend',headers=headers,query_string=delete_params)
            result_json = await result.get_json()
            assert result.status_code == 200
            assert result_json['status'] == 'success'
            assert result_json['message']['friends'] == []