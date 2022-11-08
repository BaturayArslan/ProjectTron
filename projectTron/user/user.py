from quart import Blueprint, g, current_app, jsonify, make_response, request
from quart_jwt_extended import jwt_required, get_raw_jwt,get_jwt_claims
from bson import ObjectId
from datetime import datetime
import async_timeout
import asyncio
import json
import aioredis

from projectTron import db
from projectTron import redis
from projectTron.utils.utils import parse_redis_stream_event
from ..exceptions import DbError, BadRequest
from ..utils.utils import redis_to_normal_timestamp,normal_to_redis_timestamp,objectid_to_str

user_bp = Blueprint('user', __name__, url_prefix='/user')


@user_bp.route('/profile', methods=['GET'])
@jwt_required
async def user_profile():
    arguments = request.args
    user_id = arguments.get('user_id', None)
    if not user_id:
        return jsonify({'message': 'user_id parameter missing.'}), 400
    user_info = await db.get_user_profile(user_id)
    return jsonify({
        'message': user_info
    }),200



@user_bp.route('/add_friend', methods=['GET'])
@jwt_required
async def add_friend():
    user = get_raw_jwt()
    arguments = request.args
    friend_id = arguments.get('friend_id', None)
    avatar = int(arguments.get('avatar')) if arguments.get('avatar') else None
    if not (friend_id or avatar):
        return jsonify({'message': 'friend_id or avatar parameter missing.'}), 400
    await db.add_friend(user["user_claims"]['user_id'], friend_id, avatar)
    updated_friends = await db.find_user(user['identity'], {'_id': 0, 'friends': 1})
    return jsonify({
        'message': objectid_to_str(updated_friends)
    })



@user_bp.route('/delete_friend', methods=['GET'])
@jwt_required
async def delete_friend():

    user = get_raw_jwt()
    arguments = request.args
    friend_id = arguments.get('friend_id', None)
    if not friend_id:
        return jsonify({'message': 'friend_id parameter missing.'}), 400
    await db.delete_friend(user["user_claims"]['user_id'], friend_id)
    updated_friends = await db.find_user(user['identity'], {'_id': 0, 'friends': 1})
    return jsonify({
        'message': updated_friends
    })



@user_bp.route('/send_message', methods=['POST'])
@jwt_required
async def send_message():
    user = get_jwt_claims()
    pubsub,redis_connection = await redis.get_redis()
    message = await request.get_json()
    friend_id = message.get('friend_id', None)
    msg = message.get('msg', None)
    timestamp = datetime.timestamp(datetime.utcnow())
    if not (friend_id or msg) or (msg == '' or friend_id == ''):
        return jsonify({'message': 'friend_id or msg or timestamp parameter missing.'}), 400
    await db.send_message(user['user_id'], friend_id, {'msg':msg,'timestamp':timestamp})

    redis.Events.set_message_sends(user['user_id'],msg,timestamp,friend_id)
    event = json.dumps(redis.Events.MESSAGE_SENDS)
    await redis_connection.xadd(name=friend_id,fields={'container':event},id=normal_to_redis_timestamp(timestamp),maxlen=30,approximate=False)

    return jsonify({
        'message': {'msg':msg,'timestamp':timestamp,'reciever':friend_id,'sender':user['user_id'],"path":"/send_message"}
    })


@user_bp.route('/get_messages', methods=['GET'])
@jwt_required
async def get_messages():

    user = get_jwt_claims()
    arguments = request.args
    friend_id = arguments.get('friend_id', None)
    if not friend_id:
        return jsonify({'message': 'friend_id parameter missing.'}), 400
    messages = await db.get_messages(user['user_id'], friend_id)
    return jsonify({
        'message': messages
    })


@user_bp.route('/update_messages', methods=['GET'])
@jwt_required
async def update_messages():
    user = get_jwt_claims()
    redis_connection = g.redis_connection
    arguments = request.args
    timestamp = float(arguments.get('timestamp')) if arguments.get('timestamp') else None
    if not timestamp:
        return jsonify({'message': 'friend_id parameter missing.'}), 400
    if(arguments.get("isBlock",True)):
        print("started : ",user['user_name'])
        new_message = await redis_connection.xreadgroup(user['user_id'],user['user_id'],{user['user_id']: ">"},block=120000000,noack=True)
        print("leaved: " ,user['user_name'])
    else:
        new_message = await redis_connection.xreadgroup(user['user_id'],user['user_id'],{user['user_id']: normal_to_redis_timestamp(timestamp)},noack=True)
    if new_message:
        return jsonify({'message': parse_redis_stream_event(new_message)}), 200
    else:
        return jsonify({'message': []}), 200




@user_bp.route('/last_opened',methods=['GET'])
async def update_last_opened():
    user = get_jwt_claims()
    friend_id = request.args.get('friend_id',None)
    if not friend_id:
        return jsonify({'message':'friend_id parameter missing.'}),400
    timestamp = await db.update_last_opened(user['user_id'],friend_id)
    return jsonify({'message':timestamp}),200