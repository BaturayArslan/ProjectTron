import asyncio
import json
import async_timeout
from quart import g, current_app
from datetime import datetime
from drawProject.utils.utils import parse_redis_stream_event


class Game:
    def __init__(self, room_id, data):
        self.players = {}
        self.connections = {}
        self._event_que = asyncio.Queue()
        self.redis_connection = g.redis_connection
        self.pubsub = g.redis_connection.pubsub()
        self.broker = Broker(self)
        self.events = Events(self)
        self._room_id = room_id
        self.max_user = data['max_user']
        self.max_round = data['max_point']

    def register(self, player_id, user_name, websocket):
        self.connections[player_id] = {
            'connection': websocket,
            'send_que': asyncio.Queue(),
            'user_name': user_name
        }
        self.connections[player_id].update({"send_task": self._create_send_task(self.connections[player_id], player_id),
                                            "receive_task": self._create_receive_task(self.connections[player_id],
                                                                                      player_id)})

        # Inform other server that new user joined a room
        player_join_event = Events.set_player_join(player_id, user_name)
        await self.broker.push_event(player_join_event)

        return self.connections[player_id]['send_task'], self.connections[player_id]['receive_task']

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
                await self.set_pubsub()
                while True:
                    event = await player['connection'].receive()
                    await self.redis_connection.xadd(self._room_id, json.loads(event), id='*', maxlen=50)
            except asyncio.CancelledError:
                raise

        return asyncio.create_task(task_fnc(player=player, player_id=player_id))

    def disconnect(self, player_id, user_name):
        player_disconnect_event = Events.set_player_leave(player_id, user_name)
        await self.broker.push_event(player_disconnect_event)

    async def set_pubsub(self):
        if not self.pubsub.subscribed:
            await self.pubsub.subscribe(self._room_id)


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

    async def get_event(self):
        raw_event = await self.game.redis_connection.xread({self.game._room_id: self.last_event_id}, block=12000000)
        if raw_event:
            event = parse_redis_stream_event(raw_event)
            return event
        return None

    async def push_event(self, event):
        await self.game.redis_connection.xadd(self.game._room_id, event, id='*', maxlen=50)


class Events():
    EVENTS_LIST = [
        (1, 'player_join'),
        (2, 'player_leave'),
        (3, 'system_message'),
        (4, 'user_message'),
        (5, 'change_color'),
        (6,'send_friend_request'),
        (7,'has_friend_request'),
        (8,'ack_friend_request')
    ]

    def __init__(self, game):
        self.game = game

    async def __call__(self, events: list):
        for event in events:
            event_number = event['event_number']
            for number, name in self.EVENTS_LIST:
                if number == event_number:
                    fnc = getattr(self, name)
                    await fnc(event)

    async def player_join(self, event):
        self.game.players[event['info']['user_id']] = {
            'user_name': event['info']['user_name'],
            'color': event['info']['color'],
            'win_round': event['info']['win_round'],
            'join_time': datetime.timestamp(datetime.utcnow())
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
            }
        }
        return event

    async def player_leave(self, event):
        self.game.players.pop(event['info']['user_id'])
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
        try:
            self.game.connections.pop(event['info']['user_id'])
            await self.game.broker.publish(result, ('broadcast', None))
        except KeyError:
            await self.game.broker.publish(result, ('broadcast', None))

    @staticmethod
    def set_player_leave(user_id, user_name):
        event = {
            'event_number': 2,
            'info': {
                'user_id': user_id,
                'user_name': user_name
            }
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
        self.game.players[event['info']['user_id']].update({"color":event['info']['color']})
        self.game.broker.publish(event,('broadcast',None))

    @staticmethod
    def set_change_color(user_id, color):
        event = {
            'event_number': 5,
            'info': {
                'user_id': user_id,
                'color': color
            }
        }
        return event

    async def send_friend_request(self,event):
        result = Events.set_has_friend_request(event['info']['to_user_id'],event['info']['user_id'])
        await self.game.broker.push_event(result)


    @staticmethod
    def set_send_friend_request(from_user_id,to_user_id):
        event = {
            'event_number': 6,
            'info':{
                'user_id': from_user_id,
                'to_user_id':to_user_id
            }
        }
        return event

    async def has_friend_request(self,event):
        try:
            await self.game.broker.publish(event,('user',event['user_id']))
        except KeyError:
            pass

    @staticmethod
    def set_has_friend_request(user_id,from_user_id):
        event = {
            'event_number': 7,
            'info':{
                'user_id':user_id,
                'from_user_id':from_user_id
            }
        }
        return event

    async def ack_friend_request(self,event):
        try:
            await self.game.broker.publish(event,('user',event['info']['user_id']))
        except KeyError:
            pass

    @staticmethod
    def set_ack_friend_request(user_id,from_user_id,answer):
        event = {
            'event_number':8,
            'info':{
                "user_id" : user_id,
                'from_user_id':from_user_id,
                'answer':answer
            }
        }