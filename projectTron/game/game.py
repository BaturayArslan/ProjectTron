import asyncio
import json
import traceback

import async_timeout
import math
from quart import g, current_app
from collections import defaultdict
from datetime import datetime
from projectTron.utils.utils import parse_redis_stream_event, bezier
from projectTron import db
from .player import Player
from ..redis import events


class Game:
	CYCLE_WIDTH = 50
	CYCLE_HEIGHT = 20
	CANVAS_WIDTH = 1200
	CANVAS_HEIGHT = 400

	def __init__(self, room_id, data):
		self.players = {}
		self.connections = {}
		self._event_que = asyncio.Queue()
		self.redis_connection = g.redis_connection
		self.pubsub = g.redis_connection.pubsub()
		self.broker = Broker(self)
		self.events = Events(self)
		self.board = Board(self, Game.CANVAS_HEIGHT, Game.CANVAS_WIDTH)
		self._room_id = room_id
		self.max_user = data['max_user']
		self.max_round = data['max_point']
		self.current_round = 0
		self.is_in_round = False
		self.is_start = False
		self.pause = True
		self.teams = defaultdict(list)
		self.break_time = 10
		self.interval = 1 / 60
		self.color_codes = ['Green', 'Red', 'Blue', 'Purple']

	async def register(self, player_id, user_name, websocket):
		self.connections[player_id] = {
			'connection': websocket,
			'send_que': asyncio.Queue(),
			'user_name': user_name,
		}
		self.connections[player_id].update({"send_task": self._create_send_task(self.connections[player_id], player_id),
											"receive_task": self._create_receive_task(self.connections[player_id],
																					  player_id)})

		await self.set_pubsub()
		# Inform other server that new user joined a room
		player_join_event = await Events.set_player_join(player_id, user_name)
		await self.broker.push_event(player_join_event)

		return self.connections[player_id]['send_task'], self.connections[player_id]['receive_task']

	async def run(self):
		try:
			game_loop_task = self._create_game_loop_task()
			while True:
				try:
					events = await self.broker.get_events()
					await self.events(events)
				except Exception as e:
					# TODO change this later.
					print(traceback.format_exc())
		except asyncio.CancelledError as e:
			game_loop_task.cancel()
			raise

	async def _run_game_loop(self):
		try:
			broadcast_game = [{'event_number': 23}]
			deltaTime = 0
			while True:
				try:
					firtsTime = datetime.timestamp(datetime.utcnow())
					if (not self.pause):
						for user_id in self.players:
							await self.players[user_id].update(deltaTime)
						await self.events(broadcast_game)
					await asyncio.sleep(self.interval)
					deltaTime = (datetime.timestamp(datetime.utcnow()) - firtsTime) * 1000
				except Exception as e:
					print(traceback.format_exc())
		except asyncio.CancelledError as e:
			raise

	def _create_send_task(self, player, player_id):
		async def task_fnc(*args, **kwargs):
			try:

				while True:
					event = await player['send_que'].get()
					await player['connection'].send(event)
			except asyncio.CancelledError:
				raise

		return asyncio.create_task(task_fnc(player=player, player_id=player_id))

	def _create_receive_task(self, player, player_id):
		async def task_fnc(*args, **kwargs):
			try:
				while True:
					event = await player['connection'].receive()
					await self.redis_connection.xadd(self._room_id, {'container': event}, id='*', maxlen=50)
			except asyncio.CancelledError:
				raise

		return asyncio.create_task(task_fnc(player=player, player_id=player_id))

	def _create_game_loop_task(self):
		return asyncio.create_task(self._run_game_loop())

	async def disconnect(self, player_id, user_name):
		self.players.pop(player_id)
		self.connections.pop(player_id)

		player_disconnect_event = Events.set_player_leave(player_id, user_name)
		await self.broker.push_event(player_disconnect_event)

		if (len(self.players) <= 1 and self.is_start):
			await self.close_game()

	async def close_game(self):

		game_task = current_app.game_tasks[self._room_id]
		game_task.cancel()
		await asyncio.gather(game_task, return_exceptions=True)

		for i in range(3, 0, -1):
			message = Events.set_system_message(f'This room gonna close after {i} second !!')
			await self.broker.publish([message], ('broadcast', None))
			await asyncio.sleep(1)

		message = Events.set_system_message('GoodBye User...')
		await self.broker.publish([message], ('broadcast', None))

		for user_id in self.players:
			await self.connections[user_id]["send_que"].put(json.dumps([{'event_number': 666}]))
		try:
			await db.delete_room(self._room_id)
			events.set_room_deletion(self._room_id)
			await g.redis_connection.publish('rooms_info_feed', json.dumps(events.ROOM_DELETION))
		except Exception as e:
			print(traceback.format_exc())
			pass
		current_app.game_tasks.pop(self._room_id)
		current_app.games.pop(self._room_id)

	async def set_pubsub(self):
		if not self.pubsub.subscribed:
			await self.pubsub.subscribe(self._room_id)

	async def update_is_start(self, state):
		self.is_start = state
		await db.change_is_start(self.is_start, self._room_id)

	async def reset_game(self, winner):
		await db.increase_win(winner)
		await db.reset_room(self._room_id)
		for player_id in self.players:
			self.players[player_id].reset()
			self.players[player_id].win_round = 0
		self.current_round = 0
		self.is_in_round = False
		self.is_start = False
		self.teams = defaultdict(list)
		self.break_time = 10
		self.color_codes = ['Green', 'Red', 'Blue', 'Purple']
		self.board.clear_board()


class Broker():
	def __init__(self, game):
		self.game = game
		self.last_event_id = 0

	async def publish(self, event, to_whom):
		# to_whom like ('broadcast',_),('group',['123dafa','fasd123']),('user','213dasd')
		key, value = to_whom
		event = json.dumps(event)
		if key == 'broadcast':
			for user_id in self.game.connections.keys():
				await self.game.connections[user_id]['send_que'].put(event)
		elif key == 'group':
			for user_id in value:
				await self.game.connections[user_id]['send_que'].put(event)
		elif key == 'user':
			await self.game.connections[value]['send_que'].put(event)

	async def get_events(self):
		raw_events = await self.game.redis_connection.xread({self.game._room_id: self.last_event_id}, block=12000000)
		self.last_event_id = raw_events[0][1][-1][0].decode('utf-8')
		events = parse_redis_stream_event(raw_events)
		return events

	async def push_event(self, event, id='*'):
		if type(event) != str:
			event = json.dumps(event)
		await self.game.redis_connection.xadd(self.game._room_id, {'container': event}, id=id, maxlen=50)


class Events():
	EVENTS_LIST = [
		(23, 'broadcast_game_state'),
		(20, "key_down"),
		(21, "key_up"),
		(22, 'toggle_trace'),
		(1, 'player_join'),
		(2, 'player_leave'),
		(3, 'system_message'),
		(4, 'user_message'),
		(5, 'change_color'),
		(6, 'send_friend_request'),
		(7, 'has_friend_request'),
		(8, 'ack_friend_request'),
		(9, 'toggle_ready'),
		(10, "start_game"),
		(11, "get_game_state"),
		(12, "start_round"),
		(13, "end_round"),
		(14, "end_game"),
		(16, "echo"),
		(17, "get_room_info"),
	]

	def __init__(self, game):
		self.game = game

	async def __call__(self, events: list):
		for event in events:
			event_number = event['event_number']
			event['timestamp'] = datetime.timestamp(datetime.utcnow())
			for number, name in self.EVENTS_LIST:
				if number == event_number:
					fnc = getattr(self, name)
					await fnc(event)

	async def player_join(self, event):
		self.game.players[event['info']['user_id']] = Player(self.game, event)

		result = [
			{
				'event_number': 1,
				'info': [self.game.players[user_id].transform_to_dict() for user_id in self.game.players]
			},
			{
				'event_number': 3,
				'message': f'User {event["info"]["user_name"]} has joined room.'
			},
			await Events.set_get_room_info(self.game._room_id)
		]
		await self.game.broker.publish(result, ('broadcast', None))

	@staticmethod
	async def set_player_join(user_id, user_name):
		player_info = await db.get_user_profile(user_id)
		event = {
			'event_number': 1,
			'info': {
				'user_id': user_id,
				'user_name': user_name,
				'win_round': 0,
				'color': 1,
				'is_ready': False,
				'avatar': player_info['avatar']
			},
			'timestamp': datetime.timestamp(datetime.utcnow())
		}
		return event

	async def player_leave(self, event):
		result = [
			{
				'event_number': 2,
				'info': [self.game.players[user_id].transform_to_dict() for user_id in self.game.players]
			},
			{
				'event_number': 3,
				'message': f'User {event["info"]["user_name"]} has leave room.'
			},
			await Events.set_get_room_info(self.game._room_id)
		]

		await self.game.broker.publish(result, ('broadcast', None))

	@staticmethod
	def set_player_leave(user_id, user_name):
		event = {
			'event_number': 2,
			'info': {
				'user_id': user_id,
				'user_name': user_name
			},
			'timestamp': datetime.timestamp(datetime.utcnow())
		}
		return event

	async def user_message(self, event):
		await self.game.broker.publish([event], ('broadcast', None))

	@staticmethod
	def set_user_message(self, user_name, user_id, msg):
		event = {
			'event_number': 4,
			'info': {
				'user_name': user_name,
				'user_id': user_id,
				'msg': msg,
				'timestamp': datetime.timestamp(datetime.utcnow())
			}
		}
		return event

	async def change_color(self, event):
		user_id = event['info']['user_id']
		new_color = event['info']['color']
		self.game.players[user_id].color = new_color
		await self.game.broker.publish([event], ('broadcast', None))

	@staticmethod
	def set_change_color(user_id, color):
		event = {
			'event_number': 5,
			'info': {
				'user_id': user_id,
				'color': color
			},
			'timestamp': datetime.timestamp(datetime.utcnow())
		}
		return event

	async def send_friend_request(self, event):
		result = Events.set_has_friend_request(event['info']['to_user_id'], event['info']['user_id'],
											   event['info']['user_name'])
		await self.game.broker.push_event(result)

	@staticmethod
	def set_send_friend_request(from_user_id, to_user_id, user_name):
		event = {
			'event_number': 6,
			'info': {
				'user_id': from_user_id,
				'user_name': user_name,
				'to_user_id': to_user_id
			},
			'timestamp': datetime.timestamp(datetime.utcnow())
		}
		return event

	async def has_friend_request(self, event):
		try:
			await self.game.broker.publish([event], ('user', event['info']['user_id']))
		except KeyError:
			pass

	@staticmethod
	def set_has_friend_request(user_id, from_user_id, from_user_name):
		event = {
			'event_number': 7,
			'info': {
				'user_id': user_id,
				'from_user_id': from_user_id,
				'from_user_name': from_user_name
			},
			'timestamp': datetime.timestamp(datetime.utcnow())
		}
		return event

	async def ack_friend_request(self, event):
		try:
			await self.game.broker.publish([event], ('user', event['info']['user_id']))
			if (event['info']['answer']):
				await db.add_friend(event['info']['user_id'], event['info']['from_user_id'])
		except KeyError:
			pass

	@staticmethod
	def set_ack_friend_request(user_id, from_user_id, from_user_name, answer):
		event = {
			'event_number': 8,
			'info': {
				"user_id": user_id,
				'from_user_id': from_user_id,
				'from_user_name': from_user_name,
				'answer': answer
			},
			'timestamp': datetime.timestamp(datetime.utcnow())
		}
		return event

	async def toggle_ready(self, event):
		user_id = event['info']['user_id']
		new_state = event['info']['is_ready']
		self.game.players[user_id].is_ready = new_state
		await self.game.broker.publish([event], ('broadcast', None))

	@staticmethod
	def set_toggle_ready(user_id, is_ready):
		event = {
			'event_number': 9,
			'info': {
				'user_id': user_id,
				'is_ready': is_ready
			},
			'timestamp': datetime.timestamp(datetime.utcnow())
		}
		return event

	async def start_game(self, event):
		# Check if loby in valid state.
		if len(self.game.players) <= 1:
			return None
		elif not await db.is_admin(event['info']['user_id'], self.game._room_id):
			return None
		elif self.game.is_start:
			return None

		for key in self.game.players:
			if not self.game.players[key].is_ready:
				return None

		# loby is in valid state set teams and game object
		self.game.is_start = True
		try:
			await self.game.update_is_start(True)
		except Exception as e:
			self.game.is_start = False
			return None

		start_positions = []
		red_team_counter = 0
		blue_team_counter = 0
		for index, key in enumerate(self.game.players):
			# Calculate teams
			player = self.game.players[key]
			self.game.teams[player.color].append(player)
			# Calculate Start Positions
			if player.color == 1:
				# Red Team
				up_or_down = red_team_counter % 2
				x = Game.CANVAS_WIDTH - Game.CYCLE_WIDTH
				y = (Game.CANVAS_HEIGHT / 2) - (red_team_counter * Game.CYCLE_HEIGHT) \
					if up_or_down == 0 else (Game.CANVAS_HEIGHT / 2) + (red_team_counter * Game.CYCLE_HEIGHT)
				rotation = 180
				player.set_start_position(x - 16, y, rotation)
				start_positions.append({'user_id': player.user_id, 'x': x - 16, 'y': y, 'rotation': rotation})
				red_team_counter += 1
			else:
				# Blue Team
				up_or_down = blue_team_counter % 2
				x = 0
				y = (Game.CANVAS_HEIGHT / 2) - (blue_team_counter * Game.CYCLE_HEIGHT) \
					if up_or_down == 0 else (Game.CANVAS_HEIGHT / 2) + (blue_team_counter * Game.CYCLE_HEIGHT)
				rotation = 0
				start_positions.append({'user_id': player.user_id, 'x': x + 16, 'y': y, 'rotation': rotation})
				player.set_start_position(x + 16, y, rotation)
				blue_team_counter += 1

		for i in range(3, 0, -1):
			message = Events.set_system_message(f'After {i} second game will start.')
			await self.game.broker.publish([message], ('broadcast', None))
			await asyncio.sleep(1)

		event['info']['start_positions'] = start_positions
		await self.game.broker.publish([event], ('broadcast', None))

		message = Events.set_system_message(f'Round Gonna Start in {self.game.break_time}')
		await self.game.broker.publish([message], ('broadcast', None))
		await asyncio.sleep(self.game.break_time)

		await self.start_round()

	@staticmethod
	def set_start_game(user_id):
		event = {
			'event_number': 10,
			'info': {
				'user_id': user_id,
			},
			'timestamp': datetime.timestamp(datetime.utcnow())
		}
		return event

	@staticmethod
	def set_system_message(message):
		event = {
			'event_number': 3,
			'message': message
		}
		return event

	async def get_game_state(self, event):
		event['info']['state'] = {
			"players": [self.game.players['user_id'].transform_to_dict() for user_id in self.game.players],
			"is_start": self.game.is_start,
			'max_round': self.game.max_round,
			'max_user': self.game.max_user,
			'room_id': self.game._room_id,
			'is_in_round': self.game.is_in_round,
			'teams': self.game.teams,
			'current_round': self.game.current_round

		}
		await self.game.broker.publish(event, ('user', event['info']['user_id']))

	@staticmethod
	def set_get_game_state(user_id, game):
		event = {
			'event_number': 11,
			'info': {
				'user_id': user_id,
			},
			'timestamp': datetime.timestamp(datetime.utcnow())
		}

	async def end_round(self, winner):
		self.game.is_in_round = False
		self.game.pause = True
		team = self.game.teams[winner]
		event = {
			'event_number': 13,
			'info': {
				'winner_color': winner,
				'players': [self.game.players[user_id].transform_to_dict() for user_id in self.game.players]
			}
		}
		message = Events.set_system_message(
			f"Theee Winner iiiis {self.game.color_codes[winner]} Team!!")
		await self.game.broker.publish([event, message], ('broadcast', None))

		for player in team:
			player.win_round += 1
			if self.game.current_round == self.game.max_round:
				return await self.end_game()

		message = Events.set_system_message(
			f"{self.game.current_round} is Finished.Next Round Gonna Start in {self.game.break_time}")
		await self.game.broker.publish([message], ('broadcast', None))
		await asyncio.sleep(self.game.break_time)
		await self.start_round()

	async def start_round(self):

		# position players at them start posiitons
		for user_id in self.game.players:
			self.game.players[user_id].reset()

		self.game.board._map = [[0 for i in range(Game.CANVAS_WIDTH)] for j in range(Game.CANVAS_HEIGHT)]

		# After this event fired game will start after 3 second.
		await self.game.broker.publish([{"event_number": 12}], ('broadcast', None))

		for i in range(3, 0, -1):
			message = Events.set_system_message(f'After {i} second round  will start.')
			await self.game.broker.publish([message], ('broadcast', None))
			await asyncio.sleep(1)

		self.game.is_in_round = True
		self.game.current_round = self.game.current_round + 1
		await db.update_round(self.game.current_round, self.game._room_id)

		message = Events.set_system_message("Fight")
		await self.game.broker.publish([message], ('broadcast', None))

		self.game.pause = False

	async def end_game(self):
		teams_point = []
		for color_code in self.game.teams:
			teams_point.append((self.game.teams[color_code][0].win_round, self.game.color_codes[color_code],
								self.game.teams[color_code]))
		teams_point.sort(key=lambda element: element[0], reverse=True)

		message = Events.set_system_message(f"Team {teams_point[0][1]} Win The Game With {teams_point[0][0]} Point")
		await self.game.broker.publish([message], ('broadcast', None))

		await asyncio.sleep(2)

		for i in range(3, 0, -1):
			message = Events.set_system_message(f'After {i} second game  will end.')
			await self.game.broker.publish([message], ('broadcast', None))
			await asyncio.sleep(1)

		await self.game.reset_game(teams_point[0][2])
		result = [
			{
				'event_number': 14,
				'info': {
					"players": [self.game.players[user_id].transform_to_dict() for user_id in self.game.players],

				}
			},
			await Events.set_get_room_info(self.game._room_id)
		]
		await self.game.broker.publish(result, ('broadcast', None))

	async def key_down(self, event):
		user_id = event['info']['user_id']
		key = event['info']['key']
		player = self.game.players[user_id]
		player.keys[key] = 0.01

	@staticmethod
	def set_key_down(key, user_id):
		event = {
			'event_number': 20,
			'info': {
				'user_id': user_id,
				'key': key,
			}
		}
		return event

	async def key_up(self, event):
		user_id = event['info']['user_id']
		key = event['info']['key']
		player = self.game.players[user_id]
		player.keys[key] = 0

	@staticmethod
	def set_key_up(key, user_id):
		event = {
			'event_number': 21,
			'info': {
				'user_id': user_id,
				'key': key,
			}
		}
		return event

	async def toggle_trace(self, event):
		user_id = event['info']['user_id']
		player = self.game.players[user_id]
		player.renderTile = False if player.renderTile else True

	@staticmethod
	def set_toggle_trace(user_id):
		event = {
			'event_number': 22,
			'info': {
				'user_id': user_id
			}
		}
		return event

	async def broadcast_game_state(self, event):
		players_arr = [self.game.players[user_id].transform_to_dict() for user_id in self.game.players]
		event = {
			'event_number': 23,
			'info': {
				'players': players_arr
			}
		}
		await self.game.broker.publish([event], ('broadcast', None))

	@staticmethod
	def set_broadcast_game_state():
		event = {
			'event_number': 23,
			'info': {
				'players': [{}, {}]
			}
		}
		return event

	async def echo(self, event):
		await self.game.broker.publish(event, ('broadcast', None))

	async def get_room_info(self):
		event = await Events.set_get_room_info(self.game._room_id)
		await self.game.broker.publish(event, ('broadcast', None))

	@staticmethod
	async def set_get_room_info(room_id):
		room_info = await db.find_room(room_id)
		event = {
			'event_number': 17,
			'info': room_info
		}
		return event


class Board:
	def __init__(self, game, rows, cols):
		self.game = game
		self._rows = rows
		self._cols = cols
		self._map = [[0 for i in range(cols)] for j in range(rows)]

	def clear_board(self):
		self._map = [[0 for i in range(self._cols)] for j in range(self._rows)]

	async def collision_detect(self, point_1, point_2, color):
		try:
			# Detec if cycle Hits Game Area Borders
			front_point_x = Game.CYCLE_WIDTH * math.cos((math.pi / 180) * point_1['rotation']) + point_1['x']
			front_point_y = Game.CYCLE_WIDTH * math.sin((math.pi / 180) * point_1['rotation']) + point_1['y']
			if front_point_x >= self._cols or front_point_x <= 0 \
					or front_point_y >= self._rows or front_point_y <= 0:
				winner = 2 if color == 1 else 1
				await self.game.events.end_round(winner)
				return True

			slope = round((point_1['y'] - front_point_y) / (point_1['x'] - front_point_x))
			# Detect if cycle hit own or another cycle's trace
			for i in range(round(min(point_1['x'], front_point_x)) + 1, round(max(point_1['x'], front_point_x))):
				y = round(slope * i - slope * point_1['x'] + point_1['y'])
				if self._map[y][i] != 0:
					winner = 2 if color == 1 else 1
					await self.game.events.end_round(winner)
					return True

			slope_2 = round((point_1['y'] - point_2['y']) / (point_1['x'] - point_2['x']))
			for i in range(round(min(point_1['x'], point_2['x'])) + 1, round(max(point_1['x'], point_2['x']))):
				y = round(slope_2 * i - slope_2 * point_1['x'] + point_1['y'])
				self._map[y][i] = color

			return False

		except IndexError as e:
			print(traceback.format_exc())
			winner = 2 if color == 1 else 1
			await self.game.events.end_round(winner)
			return True

	def clear_trace(self, point_1, point_2):
		try:
			slope = round((point_2['y'] - point_1['y']) / (point_2['x'] - point_1['x']))
			for i in range(round(min(point_1['x'], point_2['x'])) + 1, round(max(point_1['x'], point_2['x']))):
				y = round(slope * i - slope * point_2['x'] + point_2['y'])
				self._map[y][i] = 0
			self._map[round(point_1['y'])][round(point_1['x'])] = 0
		except ZeroDivisionError as e:
			for i in range(round(min(point_1['y'], point_2['y'])) + 1, round(max(point_1['y'], point_2['y']))):
				self._map[i][round(point_1['x'])] = 0
			self._map[round(point_1['y'])][round(point_1['x'])] = 0
			print(traceback.format_exc())
