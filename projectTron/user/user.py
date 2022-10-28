from quart import Blueprint, g, current_app, jsonify, make_response, request
from flask_jwt_extended import jwt_required, get_jwt
from bson import ObjectId
from datetime import datetime
import async_timeout
import asyncio
import json

from projectTron import db
from projectTron import redis
from projectTron.utils.utils import parse_redis_stream_event
from ..exceptions import DbError, BadRequest
from ..utils.utils import redis_to_normal_timestamp,normal_to_redis_timestamp,objectid_to_str
user_bp = Blueprint('user', __name__, url_prefix='/user')


@user_bp.route('/profile', methods=['GET'])
@jwt_required()
async def user_profile():
    try:
        arguments = request.args
        user_id = arguments.get('user_id', None)
        if not user_id:
            return jsonify({'status': 'error', 'message': 'user_id parameter missing.'}), 400
        user_info = await db.get_user_profile(user_id)
        return jsonify({
            'status': 'success',
            'message': user_info
        }),200
    except Exception as e:
        raise e


@user_bp.route('/add_friend', methods=['GET'])
@jwt_required()
async def add_friend():
    try:
        user = get_jwt()
        arguments = request.args
        friend_id = arguments.get('friend_id', None)
        avatar = int(arguments.get('avatar')) if arguments.get('avatar') else None
        if not (friend_id or avatar):
            return jsonify({'status': 'error', 'message': 'friend_id or avatar parameter missing.'}), 400
        await db.add_friend(user['user_id'], friend_id, avatar)
        updated_friends = await db.find_user(user['sub'], {'_id': 0, 'friends': 1})
        return jsonify({
            'status': 'success',
            'message': objectid_to_str(updated_friends)
        })
    except Exception as e:
        raise e


@user_bp.route('/delete_friend', methods=['GET'])
@jwt_required()
async def delete_friend():
    try:
        user = get_jwt()
        arguments = request.args
        friend_id = arguments.get('friend_id', None)
        if not friend_id:
            return jsonify({'status': 'error', 'message': 'friend_id parameter missing.'}), 400
        await db.delete_friend(user['user_id'], friend_id)
        updated_friends = await db.find_user(user['sub'], {'_id': 0, 'friends': 1})
        return jsonify({
            'status': 'success',
            'message': updated_friends
        })
    except DbError as e:
        jsonify({
            'status': 'error',
            'message': f'{str(e)}'
        }), 500
    except Exception as e:
        raise e


@user_bp.route('/send_message', methods=['POST'])
@jwt_required()
async def send_message():
    try:
        user = get_jwt()
        pubsub,redis_connection = await redis.get_redis()
        message = await request.get_json()
        friend_id = message.get('friend_id', None)
        msg = message.get('msg', None)
        timestamp = datetime.timestamp(datetime.utcnow())
        if not (friend_id or msg) or (msg == '' or friend_id == ''):
            return jsonify({'status': 'error', 'message': 'friend_id or msg or timestamp parameter missing.'}), 400
        await db.send_message(user['user_id'], friend_id, {'msg':msg,'timestamp':timestamp})

        redis.Events.set_message_sends(user['user_id'],msg,timestamp,friend_id)
        event = json.dumps(redis.Events.MESSAGE_SENDS)
        await redis_connection.xadd(name=friend_id,fields={'container':event},id=normal_to_redis_timestamp(timestamp),maxlen=30)

        return jsonify({
            'status': 'success',
            'message': {'msg':msg,'timestamp':timestamp,'reciever':friend_id,'sender':user['user_id']}
        })
    except DbError as e:
        jsonify({
            'status': 'error',
            'message': f'{str(e)}'
        }), 500
    except Exception as e:
        raise e

@user_bp.route('/get_messages', methods=['GET'])
@jwt_required()
async def get_messages():
    try:
        user = get_jwt()
        arguments = request.args
        friend_id = arguments.get('friend_id', None)
        if not friend_id:
            return jsonify({'status': 'error', 'message': 'friend_id parameter missing.'}), 400
        messages = await db.get_messages(user['user_id'], friend_id)
        return jsonify({
            'status':'success',
            'message': messages
        })
    except DbError as e:
        jsonify({
            'status': 'error',
            'message': f'{str(e)}'
        }), 500
    except Exception as e:
        raise e


@user_bp.route('/update_messages', methods=['GET'])
@jwt_required()
async def update_messages():
    try:
        user = get_jwt()
        pubsub,redis_connection = await redis.get_redis()
        arguments = request.args
        timestamp = float(arguments.get('timestamp')) if arguments.get('timestamp') else None
        if not timestamp:
            return jsonify({'status': 'error', 'message': 'friend_id parameter missing.'}), 400

        new_message  = await redis_connection.xread({user['user_id']:normal_to_redis_timestamp(timestamp)})
        if len(new_message) != 0:
            return jsonify({'status':'success','message':parse_redis_stream_event(new_message)}),200
        else:
            async with async_timeout.timeout(120.0):
                new_message = await redis_connection.xread({user['user_id']: normal_to_redis_timestamp(timestamp)},block=110000)
                return jsonify({'status': 'success', 'message': parse_redis_stream_event(new_message) }), 200



    except DbError as e:
        jsonify({
            'status': 'error',
            'message': f'{str(e)}'
        }), 500
    except asyncio.TimeoutError as e:
        return jsonify({'status':'error','messsage': 'timeout.'}), 400
    except Exception as e:
        raise e

# TODO :: implement an endponit for updating last_opened field
@user_bp.route('/last_opened',methods=['GET'])
async def update_last_opened():
    user = get_jwt()
    friend_id = request.args.get('friend_id',None)
    if not friend_id:
        return jsonify({'message':'friend_id parameter missing.'}),400
    timestamp = await db.update_last_opened(user['user_id'],friend_id)
    return jsonify({'message':timestamp}),200