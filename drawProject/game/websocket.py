import asyncio
import json
from quart import g,current_app,websocket,Blueprint,jsonify
from flask_jwt_extended import decode_token,get_jwt,jwt_required

from drawProject import db
from drawProject import redis
from drawProject.exceptions import DbError

websocket_bp = Blueprint("websocket", __name__, url_prefix="/ws")

async def join_room(room_id,user):
    try:
        # Check if user already in a room.Validate user have a right to create room.
        await db.check_user(user['user_id'])
        room_info = await db.find_room(room_id, {'status': 1, 'admin': 1})
        args = websocket.args.to_dict()
        if websocket.args.get('password','') != room_info['status']['password']:
            return jsonify({
                'status': 'error',
                'message': 'Wrong Password.'
            }), 202
        await db.join_user_to_room(user['user_id'], room_id, room_info)

        # Publish an event for refresh_room_info view subscribers.
        redis.Events.set_user_join(room_id)
        await g.redis_connection.publish('rooms_info_feed', json.dumps(redis.Events.USER_JOIN))

        return True

    except DbError as e:
        return jsonify({"status": "error", "message": f"{str(e)}"}), 500
    except Exception as e:
        raise e

async def leave_room(user,room_id):

    #TODO :: Save user stats  to database before leave
    pubsub,redis_connection = await redis.get_redis()
    result = await db.leave_user_from_room(user['user_id'],room_id)

    # Publish an event for refresh_room_info view subscribers.
    redis.Events.set_user_laeves(room_id)
    await g.redis_connection.publish('rooms_info_feed', json.dumps(redis.Events.USER_LEAVES))

    return True

@websocket_bp.websocket('/room/<string:room_id>')
async def ws(room_id):
    try:
        headers = websocket.headers
        token = headers['Authorization'].split('Bearer ')[1]
        user = decode_token(token)

        await redis.get_redis()

        await join_room(room_id,user)

        game = current_app.games[room_id]
        receive_task,send_task = await game.register(user['user_id'],user['user_name'],websocket)
        await receive_task
        await send_task
    except asyncio.CancelledError as e:
        # Clean up when user disconnect.
        try:
            print('clean up ')
            await leave_room(user,room_id)
            await game.disconnect(user['user_id'],user['user_name'])
            await _cancel_task((receive_task,send_task),raise_exp=True)
            raise
        except NameError:
            pass
        except DbError:
            pass


async def _cancel_task(tasks,raise_exp=False):
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks,return_exceptions=True)
    if raise_exp:
        _raise_exceptions(tasks)

def _raise_exceptions(tasks):
    # Raise any unexpected exceptions
    for task in tasks:
        if not task.cancelled() and task.exception() is not None:
            raise task.exception()
