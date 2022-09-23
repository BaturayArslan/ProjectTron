import click
import os
import jwt
from quart import g, current_app
from werkzeug.local import LocalProxy
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from datetime import datetime
from flask_jwt_extended.exceptions import NoAuthorizationError
from flask_jwt_extended import decode_token
from datetime import datetime

from .exceptions import DbError, BadRequest, RoomCreationFailed, UserJoinRoomFailed


def get_db():
    if 'db' not in g:
        g.db = AsyncIOMotorClient(
            current_app.config['MONGO_URI'],
            connectTimeoutMS=5000,
            wTimeoutMS=5000,
            maxPoolSize=10,
        )[current_app.config['DATABASE_NAME']]

    return g.db


# Reach get_db method when application context installed (I think!)
db = LocalProxy(get_db)


async def register_user(data):
    """
    data{
        "email": str,
        "username":str,
        "password": str,
        "country": str | ""
        "avatar": int

    }
    """
    aditional_info = {
        "last_login": datetime.utcnow(),
        "correnct_answer": 0,
        "total_win": 0,
        "friends": []
    }
    data.update(aditional_info)
    result = await db.users.insert_one(data)
    if result.acknowledged:
        return result
    else:
        raise DbError('Couldnt Register User.')


async def find_user(email, project):
    result = await db.users.find_one({'email': email}, project)
    if result is not None:
        return result
    else:
        raise DbError('Please Try Again.')


async def create_login_session(token, email, user_id):
    decoded_token = jwt.decode(token, current_app.config.get('JWT_SECRET_KEY'), algorithms="HS256")

    result = await db.sessions.insert_one({
        "jti": decoded_token['jti'],
        "user_email": email,
        "user_id": user_id
    })
    if result.acknowledged:
        return result
    else:
        raise DbError('Couldnt Create Session.')


async def logout_user(token):
    if token:
        decoded_token = decode_token(token)
        result = await db.sessions.delete_one({'user_email': decoded_token['sub'], 'jti': decoded_token['jti']})
        if result.deleted_count == 1:
            return True
        else:
            raise DbError('error occured when logout')
    else:
        raise BadRequest('Missing refresh token.')


async def find_refresh_token(token):
    result = await db.sessions.find_one({'user_email': token['sub'], 'jti': token['jti']}, {"_id": 1})
    if result is not None:
        return True
    else:
        raise DbError('refresh token revoked.')


async def create_room(data):
    result = await db.rooms.insert_one(data)
    if result.acknowledged:
        return result
    else:
        raise DbError('Couldnt Create Room.')


async def delete_room(room_id):
    result = await db.rooms.delete_one({'_id': ObjectId(room_id)})
    if result.deleted_count == 1:
        return True
    else:
        raise DbError('Couldnt Delete Room.')


async def find_room(id, project=None):
    result = await db.rooms.find_one({"_id": ObjectId(id)}, project)
    if result is not None:
        return result
    else:
        raise DbError('Couldnt Find Room.')


async def get_rooms_info():
    cursor = db.rooms.find({}, {'status.password': 0})
    result = await cursor.to_list(length=50)
    if len(result) != 0:
        return result
    else:
        raise DbError('There is no room.')


async def check_user(id):
    cursor = db.rooms.find({"users._id": ObjectId(id)}, {'_id': 1})
    result = await cursor.to_list(length=100)
    if len(result) == 0:
        return True
    else:
        raise DbError('You Already in a room.')


async def join_user_to_room(user_id, room_id, room_info=None):
    data = {
        '_id': ObjectId(user_id),
        'point': 0,
        "color": 0,
        'win_count': 0,
        'kick_vote': 0,
    }
    if not room_info:
        room_info = await db.rooms.find_one({"_id": ObjectId(room_id)}, {'admin': 1})

    if room_info['admin']:
        result = await db.rooms.update_one({'_id': ObjectId(room_id)},
                                           {"$push": {"users": data}})
    else:
        result = await db.rooms.update_one({'_id': ObjectId(room_id)},
                                           {"$push": {"users": data}, "$set": {'admin': ObjectId(user_id)}})
    if result.modified_count == 1:
        return result
    else:
        raise UserJoinRoomFailed('Couldnt Joing User To Room.')


async def leave_user_from_room(user_id, room_id):
    room_info = db.rooms.find_one({'_id': ObjectId(room_id)}, {'admin': 1, 'users': 1})
    if len(room_info['users']) == 1:
        result = await db.rooms.update_one({'_id': ObjectId(room_id)}, {'$set': {'admin': None, 'users': []}})
    elif room_info['admin'] == ObjectId(user_id):
        result = await db.rooms.update_one({'_id': ObjectId(room_id)}, {"$pull": {"users": {"_id": ObjectId(user_id)}},
                                                                        '$set': {'admin': room_info['users'][1]}})
    else:
        result = await db.rooms.update_one({'_id': ObjectId(room_id)}, {"$pull": {"users": {"_id": ObjectId(user_id)}}})

    if result.modified_count == 1:
        return result
    else:
        raise DbError('Couldnt leave room.')

async def get_user_profile(user_id):
    result = await db.users.find({'_id': ObjectId(user_id)}, {'password': 0})
    if result is not None:
        return result
    else:
        raise DbError('User profile Counldt find.')


async def add_friend(user_id, friend_id, avatar):
    data = {
        '_id': ObjectId(friend_id),
        'avatar': avatar,
        'messages': []
    }
    result = await db.users.update_one({'_id': ObjectId(user_id)}, {'$push': {'friends': data}})
    if result.modified_count == 1:
        return result
    else:
        raise DbError('Couldnt Add friend.')


async def delete_friend(user_id, friend_id):
    result = await db.users.update_one({'_id': ObjectId(user_id)}, {"$pull": {"friends": {"_id": ObjectId(friend_id)}}})
    if result.modified_count == 1:
        return result
    else:
        raise DbError('Couldnt Delete friend.')


async def send_message(user_id, friend_id, message):
    result = db.users.update_one(
        {'_id': ObjectId(user_id), "friends": {"$elemMatch": {"friend_id": ObjectId(friend_id)}}},
        {"$push": {"friends.$.messages": message}})
    if result.modified_count == 1:
        return result
    else:
        raise DbError('Couldnt send message.')


async def get_messages(user_id, friend_id):
    result = await db.users.find(
        {'_id': ObjectId(user_id), "friends": {"$elemMatch": {"friend_id": ObjectId(friend_id)}}},
        {'friends.messages': 1}
    )
    result_2 = await db.users.update_one(
        {'_id': ObjectId(user_id), "friends": {"$elemMatch": {"friend_id": ObjectId(friend_id)}}},
        {'$set': {'friends.$.last_opened': datetime.timestamp()}}
    )
    if result is not None and result_2.modified_count == 1:
        return result
    else:
        raise DbError('Couldnt read messages')

#
# def close_db(e=None):
#     db = g.pop('db', None)
#
#     if db is not None:
#         db.close()
#
#
# def init_app(app):
#     app.teardown_appcontext(close_db)
