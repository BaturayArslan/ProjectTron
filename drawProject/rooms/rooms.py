from quart import Blueprint, request, jsonify,g,current_app
from flask_jwt_extended import jwt_required, get_jwt
from .room_forms import CreateRoomForm
from bson import ObjectId
import aioredis
import async_timeout
import asyncio
import json



from ..exceptions import DbError,RoomCreationFailed,UserJoinRoomFailed
from ..utils.utils import string_to_int
from drawProject import db
from drawProject import redis
from ..game.game import Game

rooms_bp = Blueprint("room", __name__, url_prefix="/room")


@rooms_bp.route("/createRoom", methods=['POST'])
@jwt_required()
async def create_room():
    try:
        user = get_jwt()
        form_data = await request.form
        data = string_to_int(form_data.to_dict())
        form = CreateRoomForm(form_data)
        #Check if user already in a room.Validate user have a right to create room.
        await db.check_user(user['user_id'])
        if form.validate():

            if data['password'] == "":
                data.pop('password')
                data.update({'status': {'public': True, 'password': ''}})
            else:
                data.update({'status': {'public': False, 'password': data['password']}})
                data.pop('password')
            data.update({
                'admin':ObjectId(user['user_id'])
            })

            result = await db.create_room(data)
            await db.join_user_to_room(user['user_id'], result.inserted_id)

            #Publish an event for refresh_room_info view subscribers.
            redis.Events.set_room_creation(result.inserted_id,data,user['user_id'])
            await g.redis_connection.publish('rooms_info_feed',json.dumps(redis.Events.ROOM_CREATION))

            current_app.games[str(result.inserted_id)] = Game(str(result.inserted_id),data)

            return jsonify({
                'status':'success',
                'message':{
                    'room_id': str(result.inserted_id)
                }
            }),201

        return jsonify({
            'status': 'error',
            'message': form.errors
        }), 400
    except UserJoinRoomFailed as e:
        await db.delete_room(result.inserted_id)
        return jsonify({
            'status':'error',
            'message': f'{str(e)}'
        }),500
    except DbError as e :
        return jsonify({"status": "error", "message": f"{str(e)}"}), 500
    except Exception as e:
        raise e

@rooms_bp.route("/<string:room_id>", methods=['POST'])
@jwt_required()
async def join_room(room_id):
    try:
        user = get_jwt()
        # Check if user already in a room.Validate user have a right to create room.
        await db.check_user(user['user_id'])
        room_info = await db.find_room(room_id,{'status':1,'admin':1})
        form_data = await request.form
        if form_data['password'] != room_info['status']['password']:
            return jsonify({
                'status': 'error',
                'message': 'Wrong Password.'
            }),202
        await db.join_user_to_room(user['user_id'],room_id,room_info)

        # Publish an event for refresh_room_info view subscribers.
        redis.Events.set_user_join(room_id)
        await g.redis_connection.publish('rooms_info_feed', json.dumps(redis.Events.USER_JOIN))

        return jsonify({
            'status':'success',
            'message':'OK'
        }),200

    except DbError as e :
        return jsonify({"status": "error", "message": f"{str(e)}"}), 500
    except Exception as e:
        raise e


@rooms_bp.route('/leaveRoom/<string:room_id>',methods=['GET'])
@jwt_required()
async def leave_room(room_id):
    try:
        #TODO :: Save user stats  to database before leave
        user = get_jwt()
        pubsub,redis_connection = await redis.get_redis()
        result = await db.leave_user_from_room(user['user_id'],room_id)

        # Publish an event for refresh_room_info view subscribers.
        redis.Events.set_user_laeves(room_id)
        await g.redis_connection.publish('rooms_info_feed', json.dumps(redis.Events.USER_LEAVES))

        return jsonify({
            'status':'success',
            'message':'OK'
        }),200

    except DbError as e:
        return jsonify({"status": "error", "message": f"{str(e)}"}), 500
    except Exception as e:
        raise e

@rooms_bp.route('/Rooms',methods=['GET'])
@jwt_required()
async def get_rooms_info():
    try:
        user = get_jwt()
        rooms_info = await db.get_rooms_info()
        return jsonify({
            "status": 'success',
            'message': rooms_info
        }),200
    except DbError as e :
        return jsonify({'status':'error','message': f'{str(e)}'}),500
    except Exception as e:
        raise e

@rooms_bp.route("/update",methods=['GET'])
@jwt_required()
async def refresh_rooms_info():
    try:
        client_time_stamp = float(request.args.get('timestamp')) if request.args.get('timestamp',None) else None
        broker = redis.broker
        if client_time_stamp is None or client_time_stamp == broker.events[-1]['timestamp']:
            async with async_timeout.timeout(120.0):
                event = await broker.subscribe()
                return jsonify({'status':'success','message':event})
        else:
            await asyncio.sleep(0.5)
            events = broker.syncronize(client_time_stamp)
            if events:
                return jsonify({'status':'success','events':events}),200
            return jsonify({'status':'error','message':'Your are too slow.'}),302

    except ValueError as e :
        return jsonify({'status':'error','message':'Invalid timestamp'}),400
    except asyncio.TimeoutError as e:
        return jsonify({'status':'error','messsage': 'timeout.'}), 408

