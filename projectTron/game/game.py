import asyncio
import json
import async_timeout
from quart import g, current_app
from collections import defaultdict
from datetime import datetime
from projectTron.utils.utils import parse_redis_stream_event
from projectTron import db


class Game:
    def __init__(self, room_id, data):
        self.players = {}
        self.connections = {}
        self._event_que = asyncio.Queue()
        self.redis_connection = g.redis_connection
        self.pubsub = g.redis_connection.pubsub()
        self.broker = Broker(self)
        self.events = Events(self)
        self.board = Board(self, 50, 50)
        self._room_id = room_id
        self.max_user = data['max_user']
        self.max_round = data['max_point']
        self.current_round = 0
        self.is_in_round = False
        self.is_start = False
        self.teams = defaultdict(list)
        self.break_time = 10
        self.color_codes = ['Blue', 'Red', 'Green', 'Purple']

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
        player_join_event = Events.set_player_join(player_id, user_name)
        await self.broker.push_event(player_join_event)

        return self.connections[player_id]['send_task'], self.connections[player_id]['receive_task']

    async def run(self):
        while True:
            try:
                events = await self.broker.get_events()
                await self.events(events)
            except KeyError:
                continue
            except Exception as e:
                # TODO change this later.
                continue

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
	

    async def disconnect(self, player_id, user_name):
        self.players.pop(player_id)
        self.connections.pop(player_id)

        player_disconnect_event = Events.set_player_leave(player_id, user_name)
        await self.broker.push_event(player_disconnect_event)

    async def set_pubsub(self):
        if not self.pubsub.subscribed:
            await self.pubsub.subscribe(self._room_id)

    async def update_is_start(self, state):
        self.is_start = state
        await db.change_is_start(self.is_start,self._room_id)

    async def remove_room(self):
        game_task = current_app.game_tasks[self._room_id]
        game_task.cancel()
        await asyncio.gather(game_task,return_exceptions=True)
        current_app.game_tasks.pop(self._room_id)
        current_app.games.pop(self._room_id)

    async def reset_game(self, winner):
        await db.increase_win(winner)
        for player_id in self.players:
            self.players[player_id].update({'win_round': 0, 'is_ready': False})
        self.current_round = 0
        self.is_in_round = False
        self.is_start = False
        self.teams = defaultdict(list)
        self.break_time = 10
        self.color_codes = ['Blue', 'Red', 'Green', 'Purple']
        self.board.clear_board()


class Broker():
    def __init__(self, game):
        self.game = game
        self.last_event_id = 0

    async def publish(self, event, to_whom):
        # to_whon like ('broadcast',_),('group',['123dafa','fasd123']),('user','213dasd')
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
        self.last_event_id=raw_events[0][1][-1][0].decode('utf-8')
        events = parse_redis_stream_event(raw_events)
        return events

    async def push_event(self, event,id='*'):
        if type(event) != str:
            event = json.dumps(event)
        await self.game.redis_connection.xadd(self.game._room_id, {'container': event}, id=id, maxlen=50)


class Events():
    EVENTS_LIST = [
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
        (15,"move"),
        (16,"echo")
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
        self.game.players[event['info']['user_id']] = {
            'user_id': event['info']['user_id'],
            'user_name': event['info']['user_name'],
            'color': event['info']['color'],
            'win_round': event['info']['win_round'],
            'is_ready': event['info']['is_ready'],
            'join_time': event['timestamp']
        }
        result = [
            {
                'event_number': 1,
                'info': self.game.players
            },
            {
                'event_number': 3,
                'message': f'User {event["info"]["user_name"]} has joined room.'
            }
        ]
        await self.game.broker.publish(result, ('broadcast', None))

    @staticmethod
    def set_player_join(user_id, user_name):
        event = {
            'event_number': 1,
            'info': {
                'user_id': user_id,
                'user_name': user_name,
                'win_round': 0,
                'color': 1,
                'is_ready': False
            },
            'timestamp': datetime.timestamp(datetime.utcnow())
        }
        return event

    async def player_leave(self, event):
        result = [
            {
                'event_number': 2,
                'info': self.game.players
            },
            {
                'event_number': 3,
                'message': f'User {event["info"]["user_name"]} has leave room.'
            }
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

    async def user_message(self, event):
        await self.game.broker.publish(event, ('broadcast', None))

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
        self.game.players[event['info']['user_id']].update({"color": event['info']['color']})
        self.game.broker.publish(event, ('broadcast', None))

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
        result = Events.set_has_friend_request(event['info']['to_user_id'], event['info']['user_id'])
        await self.game.broker.push_event(result)

    @staticmethod
    def set_send_friend_request(from_user_id, to_user_id):
        event = {
            'event_number': 6,
            'info': {
                'user_id': from_user_id,
                'to_user_id': to_user_id
            },
            'timestamp': datetime.timestamp(datetime.utcnow())
        }
        return event

    async def has_friend_request(self, event):
        try:
            await self.game.broker.publish(event, ('user', event['user_id']))
        except KeyError:
            pass

    @staticmethod
    def set_has_friend_request(user_id, from_user_id):
        event = {
            'event_number': 7,
            'info': {
                'user_id': user_id,
                'from_user_id': from_user_id
            },
            'timestamp': datetime.timestamp(datetime.utcnow())
        }
        return event

    async def ack_friend_request(self, event):
        try:
            await self.game.broker.publish(event, ('user', event['info']['user_id']))
        except KeyError:
            pass

    @staticmethod
    def set_ack_friend_request(user_id, from_user_id, answer):
        event = {
            'event_number': 8,
            'info': {
                "user_id": user_id,
                'from_user_id': from_user_id,
                'answer': answer
            },
            'timestamp': datetime.timestamp(datetime.utcnow())
        }
        return event

    async def toggle_ready(self, event):
        self.game.players[event['info']['is_ready']] = event['info']['is_ready']
        self.game.broker.publish(event, ('broadcast', None))

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
        if len(self.game.players) == 1 or len(self.game.players) == 0:
            return None

        elif not await db.is_admin(event['info']['user_id'], self.game._room_id):
            return None

        for key in self.game.players:
            if not self.game.players[key]['isready']:
                return None

        # loby is in valid state set teams and game object
        for key in self.game.players:
            player = self.game.players[key]
            self.game.teams[player['color']].append(player)

        for i in range(3, 0, -1):
            message = Events.set_system_message(f'After {i} second game will start.')
            await self.game.broker.publish(message, ('broadcast', None))
            await asyncio.sleep(1)

        message = Events.set_system_message("GAME HAS BEGAN.")
        try:
            self.game.update_is_start(True)
            await self.game.broker.publish(({'event_number': 10}, message), ('broadcast', None))
        except Exception as e:
            return None

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
            "players": self.game.players,
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

    async def end_round(self, winner, looser):
        self.game.is_in_round = False
        team = self.game.teams[winner]
        for player in team:
            player['win_round'] += 1
            if self.game.current_round > self.game.max_round:
                return await self.end_game()
        event = {
            'event_number': 13,
            'info': {
                "players": self.game.players,
                "is_start": self.game.is_start,
                'max_round': self.game.max_round,
                'max_user': self.game.max_user,
                'room_id': self.game._room_id,
                'is_in_round': self.game.is_in_round,
                'teams': self.game.teams,
                'current_round': self.game.current_round
            }
        }

        message = Events.set_system_message(
            f"{self.game.current_round} is Finished.Next Round Gonna Start in {self.game.break_time}")
        await self.game.broker.publish((event, message), ('broadcast', None))
        await asyncio.sleep(self.game.break_time)
        await self.start_round()

    async def start_round(self):

        for i in range(3, 0, -1):
            message = Events.set_system_message(f'After {i} second round  will start.')
            await self.game.broker.publish(message, ('broadcast', None))
            await asyncio.sleep(1)

        self.game.is_in_round = True
        self.game.current_round = self.game.current_round + 1
        await db.update_round(self.game.current_round,self.game._room_id)
        await self.game.broker.publish({"event_number": 12}, ('broadcast', None))

        message = Events.set_system_message("Fight")
        await self.game.broker.publish(message, ('broadcast', None))

    async def end_game(self):
        teams_point = []
        for color_code in self.game.teams:
            teams_point.append((self.game.teams[color_code][0]['win_round'], self.game.color_codes[color_code],
                                self.game.teams[color_code]))
        teams_point.sort(key=lambda element: element[0])

        message = Events.set_system_message(f"Team {teams_point[0][1]} Win The Game With {teams_point[0][0]}")
        await self.game.broker.publish(message, ('broadcast', None))

        await asyncio.sleep(2)

        for i in range(3, 0, -1):
            message = Events.set_system_message(f'After {i} second game  will end.')
            await self.game.broker.publish(message, ('broadcast', None))
            await asyncio.sleep(1)

        self.game.reset_game(teams_point[0][2])
        event = {
            'event_number': 14,
            'info': {
                "players": self.game.players,
                "is_start": self.game.is_start,
                'max_round': self.game.max_round,
                'max_user': self.game.max_user,
                'room_id': self.game._room_id,
                'is_in_round': self.game.is_in_round,
                'teams': self.game.teams,
                'current_round': self.game.current_round
            }
        }
        await self.game.broker.publish(event, ('broadcast', None))

    async def move(self,event):
        if not self.game.is_start or not self.game.is_in_round:
            return

        await self.game.board.set_point(event['info']['x'],event['info']['y'],event['info']['color'])

        if self.game.is_start and self.game.is_in_round:
            await self.game.broker.publish(event,('broadcast',None))

    @staticmethod
    def set_move(user_id,x,y,color):
        event = {
            'event_number':15,
            'info': {
                'user_id':user_id,
                'x':x,
                'y':y,
                'color':color
            }
        }

    async def echo(self,event):
        await self.game.broker.publish(event,('broadcast',None))

class Board:
    def __init__(self, game, rows, cols):
        self.game = game
        self._rows = rows
        self._cols = cols
        self._map = [[0 for i in range(rows)] for j in range(cols)]

    def clear_board(self):
        self._map = [[0 for i in range(self._rows)] for j in range(self._cols)]

    async def set_point(self, x, y, color):
        point = self._map[y][x]
        if point == 0:
            self._map[y][x] = color
        else:
            await self.collision_detected(point, color)

    async def collision_detected(self, point, color):
        await self.game.events.end_round(point,color)
