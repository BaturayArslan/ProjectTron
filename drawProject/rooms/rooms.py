from quart import Blueprint, request, jsonify,g,current_app
from flask_jwt_extended import jwt_required, get_jwt
from .room_forms import CreateRoomForm
from bson import ObjectId
import aioredis
import async_timeout
import asyncio


from ..exceptions import DbError
from drawProject import db
from drawProject import redis

rooms_bp = Blueprint("room", __name__, url_prefix="/room")


@rooms_bp.route("/createRoom", methods=['POST'])
@jwt_required()
async def create_room():
    try:
        user = get_jwt()
        form_data = await request.form
        data = form_data.to_dict()
        form = CreateRoomForm(form_data)
        if form.validate():
            if data['password'] == "":
                data.pop('password')
                data.update({'status': {'public': True, 'password': None}})
            else:
                data.update({'status': {'public': False, 'password': data['password']}})
                data.pop('password')
            data.update({
                'admin':ObjectId(data['admin'])
            })
            result = await db.create_room(data)
            await db.check_user(user['_id'])
            await db.join_user_to_room(user['_id'], result.inserted_id)
            # TODO establish a websocket connection

        return jsonify({
            'status': 'error',
            'message': form.errors
        }), 400
    except DbError as e :
        return jsonify({"status": "error", "message": f"{str(e)}"}), 500
    except Exception as e:
        raise e

@rooms_bp.route("/<int:room_id>", methods=['GET','POST'])
@jwt_required()
async def join_room(room_id):
    if request.method == 'GET':
        return jsonify({'message':room_id})
    try:
        user = get_jwt()
        room = await db.find_room(room_id,{'status':1})
        form_data = await request.form
        if form_data['password'] != room['status']['password']:
            return jsonify({
                'status': 'error',
                'message': 'Wrong Password.'
            }),202
        await db.check_user(user['_id'])
        await db.join_user_to_room(user['_id'],room_id)
        # TODO estanblish a websocket connection

    except DbError as e :
        return jsonify({"status": "error", "message": f"{str(e)}"}), 500
    except Exception as e:
        raise e

@rooms_bp.route("/update",methods=['GET'])
@jwt_required()
async def refresh_rooms_info():
    try:
        pubsub : aioredis.client.PubSub = g.redis_rooms_pubsub
        while True:
            async with async_timeout.timeout(120.0):
                message = await pubsub.get_message(ignore_subscribe_messages=True)
                print(message)
                """
                    rooms_info = db.get_rooms_info()
                    jsonify({'status':'success','message':rooms_info})
                """
    except asyncio.TimeoutError as e:
        return jsonify({'messsage':'timeout.'}),200
