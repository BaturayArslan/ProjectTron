from unittest import result
import click
import os
import jwt
from quart import g, current_app
from werkzeug.local import LocalProxy
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import UpdateOne
from bson import ObjectId
from datetime import datetime
from quart_jwt_extended.exceptions import NoAuthorizationError
from quart_jwt_extended import decode_token
from datetime import datetime
from projectTron.utils.utils import objectid_to_str

from .exceptions import DbError, BadRequest, RoomCreationFailed, UserJoinRoomFailed, CheckFailed


def get_db():
    if 'db' not in g:
        g.db = current_app.database_connection_pool
    return g.db


# Reach get_db method when application context installed (I think!)
db = LocalProxy(get_db)


async def register_user(data):
    """
    data{
        "email": str,
        "username":str,
        "password": str,optional (oauth player doesnt have password)
        "country": str | ""
        "avatar": int

    }
    """
    aditional_info = {
        "last_login": datetime.timestamp(datetime.utcnow()),
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
        raise DbError('Email or Password is incorrect.')


async def create_login_session(token, email, user_id):
    decoded_token = jwt.decode(token, current_app.config.get('JWT_SECRET_KEY'), algorithms="HS256")

    result = await db.sessions.insert_one({
        "jti": decoded_token['jti'],
        "user_email": email,
        "user_id": user_id
    })
    await db.users.update_one({"_id": ObjectId(user_id)},
                              {'$set': {"last_login": datetime.timestamp(datetime.utcnow())}})
    if result.acknowledged:
        return result
    else:
        raise DbError('Couldnt Create Session.')


async def logout_user(token):
    if token:
        decoded_token = decode_token(token)
        result = await db.sessions.delete_one({'user_email': decoded_token['identity'], 'jti': decoded_token['jti']})
        if result.deleted_count == 1:
            return True
        else:
            raise DbError('error occured when logout')
    else:
        raise BadRequest('Missing refresh token.')


async def find_refresh_token(token):
    result = await db.sessions.find_one({'user_email': token['identity'], 'jti': token['jti']}, {"_id": 1})
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


async def delete_player(room_id, user_id):
    result = await db.rooms.update_one({"_id": ObjectId(room_id)}, {'$pull': {}})


async def find_room(id, project=None):
    result = await db.rooms.find_one({"_id": ObjectId(id)}, project)
    if result is not None:
        return objectid_to_str(result)
    else:
        raise DbError('Couldnt Find Room.')


async def get_rooms_info():
    cursor = db.rooms.find({}, {'status.password': 0})
    result = await cursor.to_list(length=50)
    parsed_result = objectid_to_str(result)
    if len(result) != 0:
        return parsed_result
    else:
        return []


async def check_user(id):
    cursor = db.rooms.find({"users._id": ObjectId(id)}, {'_id': 1})
    result = await cursor.to_list(length=100)
    if len(result) <= 1:
        return True
    else:
        raise CheckFailed('You Already in a another room.')


async def join_user_to_room(user_id, room_id, room_info=None):
    data = {
        '_id': ObjectId(user_id),
        'point': 0,
        "color": 0,
        'win_count': 0,
        'kick_vote': 0,
    }
    if not room_info:
        room_info = await db.rooms.find_one({"_id": ObjectId(room_id)}, {'status.password': 0})

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
    room_info = await db.rooms.find_one({'_id': ObjectId(room_id), "users": {"$elemMatch": {"_id": ObjectId(user_id)}}},
                                        {'admin': 1, 'users': 1})
    if room_info is None:
        raise DbError('You are not in a room.')
    if len(room_info['users']) == 1:
        result = await db.rooms.update_one({'_id': ObjectId(room_id)}, {'$set': {'admin': None, 'users': []}})
    elif room_info['admin'] == ObjectId(user_id):
        result = await db.rooms.update_one({'_id': ObjectId(room_id)}, {"$pull": {"users": {"_id": ObjectId(user_id)}},
                                                                        '$set': {'admin': room_info['users'][1]['_id']}})
    else:
        result = await db.rooms.update_one({'_id': ObjectId(room_id)}, {"$pull": {"users": {"_id": ObjectId(user_id)}}})

    if result.modified_count == 1:
        return result
    else:
        raise DbError('Couldnt leave room.')


async def get_user_profile(user_id):
    result = await db.users.find_one({'_id': ObjectId(user_id)}, {'password': 0, 'friends.messages': 0})
    parsed_result = objectid_to_str(result)
    if result is not None:
        return parsed_result
    else:
        raise DbError('User profile Counldt find.')


async def add_friend(user1, user2):
    user1_info = await db.users.find_one({"_id": ObjectId(user1)})
    user2_info = await db.users.find_one({"_id": ObjectId(user2)})
    data1 = {
        "_id":ObjectId(user2),
        "avatar":user2_info['avatar'],
        "username":user2_info['username'],
        'last_opened': datetime.timestamp(datetime.utcnow()),
        'messages':[],
    }
    data2 = {
        "_id": ObjectId(user1),
        "avatar": user1_info['avatar'],
        "username": user1_info['username'],
        'last_opened': datetime.timestamp(datetime.utcnow()),
        'messages': [],
    }
    request = [
        UpdateOne({"_id":ObjectId(user1)},{"$push":{"friends":data1}}),
        UpdateOne({"_id": ObjectId(user2)}, {"$push": {"friends": data2}}),

    ]
    result = await db.users.bulk_write(request)

    if result.modified_count == 2:
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
    request = [
        UpdateOne({'_id': ObjectId(user_id), "friends": {"$elemMatch": {"_id": ObjectId(friend_id)}}},
                  {"$push": {"friends.$.messages": dict(message, isFromMe=True)}}),
        UpdateOne({'_id': ObjectId(friend_id), "friends": {"$elemMatch": {"_id": ObjectId(user_id)}}},
                  {"$push": {"friends.$.messages": dict(message, isFromMe=False)}})
    ]
    result = await db.users.bulk_write(request)
    if result.modified_count == 2:
        return result
    else:
        raise DbError('Couldnt send message.')


async def get_messages(user_id, friend_id):
    cursor = db.users.aggregate(
        [
            {
                '$match': {
                    '_id': ObjectId(user_id)
                }
            },
            {
                '$unwind': '$friends'
            },
            {
                '$project': {
                    'friends._id': 1,
                    'friends.avatar': 1,
					'friends.last_opened':1,
                    'friends.messages': {
                        '$slice': [
                            {
                                '$filter': {
                                    'input': '$friends.messages',
                                    'as': 'message',
                                    'cond': {

                                    }
                                }
                            }, -10
                        ]
                    }
                }
            },
            {
                '$match': {
                    'friends._id': ObjectId(friend_id)
                }
            }
        ]
    )
    result = await cursor.to_list(length=None)
    result_2 = await db.users.update_one(
        {'_id': ObjectId(user_id), "friends": {"$elemMatch": {"_id": ObjectId(friend_id)}}},
        {'$set': {'friends.$.last_opened': datetime.timestamp(datetime.utcnow())}}
    )
    if len(result) != 0:
        return objectid_to_str(result)
    else:
        raise DbError('Couldnt read messages')


async def is_admin(user_id, room_id):
    result = await db.rooms.find_one({"_id": ObjectId(room_id)}, {'admin': 1})
    if str(result['admin']) == user_id:
        return True
    return False


async def change_is_start(state, room_id):
    result = await db.rooms.update_one({'_id': ObjectId(room_id)}, {'$set': {"status.is_start": state}})
    if result.modified_count == 1:
        return result
    else:
        raise DbError('Could Change is_start status.')


async def increase_win(winner):
    request = [UpdateOne({'_id': ObjectId(player['user_id'])}, {'$inc': {'total_win': 1}}) for player in winner]
    if len(request) != 0:
        await db.users.bulk_write(request)


async def complete_login(data, email):
    aditional_info = {
        "last_login": datetime.utcnow(),
        "total_win": 0,
        "email": email,
        "friends": []
    }

    data.update(aditional_info)
    result = await db.users.replace_one({'email': email}, data)

    if result.modified_count == 1:
        return True
    else:
        DbError('Couldn Complete Login')


async def update_round(round, room_id):
    result = await db.rooms.update_one({"_id": ObjectId(room_id)}, {'$set': {'status.current_round': int(round)}})
    if result.modified_count == 1:
        return True
    else:
        DbError('Couldnt Update current_round')


async def update_last_opened(user_id, friend_id):
    timestamp = datetime.timestamp(datetime.utcnow())
    result = await db.users.update_one(
        {'_id': ObjectId(user_id), "friends": {"$elemMatch": {"_id": ObjectId(friend_id)}}},
        {'$set': {'friends.$.last_opened': timestamp}}
    )
    if result.modified_count == 1:
        return timestamp
    else:
        DbError('Couldn Update last_opened')
