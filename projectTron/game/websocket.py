import asyncio
import json
from quart import g,current_app,websocket,Blueprint,jsonify,make_response
from quart_jwt_extended import decode_token

from projectTron import db
from projectTron import redis
from projectTron.exceptions import DbError,CheckFailed

websocket_bp = Blueprint("websocket", __name__, url_prefix="/ws")

async def join_room(room_id,user):
	try:
		args = websocket.args.to_dict()
		room_info = await db.find_room(room_id)
		if websocket.args.get('password','') != room_info['status']['password'] or room_info['status']['is_start'] is True or len(room_info.get('users',[])) >= room_info['max_user'] :
			return jsonify({
				'message': 'Couldnt Join Room.Room is full or game is start'
			}), 202
		for room_user in room_info.get('users',[]):
			if str(room_user['_id']) == user['user_claims']['user_id']:
				return jsonify({
					'message': 'Your are already in this room.'
				}), 202
		await db.join_user_to_room(user['user_claims']['user_id'], room_id, room_info)
		await db.check_user(user['user_claims']['user_id'])

		# Publish an event for refresh_room_info view subscribers.
		redis.Events.set_user_join(room_id)
		await g.redis_connection.publish('rooms_info_feed', json.dumps(redis.Events.USER_JOIN))


	except CheckFailed as e:
		await db.leave_user_from_room(user['user_id'],room_id)
		raise e


async def leave_room(user,room_id):

	#TODO :: Save user stats  to database before leave
	pubsub,redis_connection = await redis.get_redis()
	result = await db.leave_user_from_room(user['user_claims']['user_id'],room_id)

	# Publish an event for refresh_room_info view subscribers.
	redis.Events.set_user_laeves(room_id)
	await g.redis_connection.publish('rooms_info_feed', json.dumps(redis.Events.USER_LEAVES))

	return True

@websocket_bp.websocket('/room/<string:room_id>')
async def ws(room_id):
	try:
		token = websocket.args.to_dict()
		user = decode_token(token['Authorization'])

		await redis.get_redis()

		is_error = await join_room(room_id,user)
		#if(is_error):
			#return is_error
		

		game = current_app.games[room_id]
		receive_task,send_task = await game.register(user['user_claims']['user_id'],user['user_claims']['user_name'],websocket)
		await receive_task
		await send_task
	except (Exception,asyncio.CancelledError) as e:
		# Clean up when user disconnect.
		print('clean up ')
		await leave_room(user,room_id)
		await game.disconnect(user['user_claims']['user_id'],user['user_claims']['user_name'])
		await _cancel_task((receive_task,send_task),raise_exp=True)
		raise e 


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
