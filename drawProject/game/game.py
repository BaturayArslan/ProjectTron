import asyncio
import json
import async_timeout
from quart import g, current_app

from drawProject.utils.utils import parse_redis_stream_event

class Game:
    def __init__(self, room_id):
        self.players = {}
        self._event_que = asyncio.Queue()
        self._room_id = room_id
        self.redis_connection = g.redis_connection
        self.pubsub = g.redis_connection.pubsub()
        self.broker = Broker(self)
        self.events = Events(self)


    def register(self, player_id, user_name, websocket):
        self.players[player_id] = {
            'connection': websocket,
            'send_que': asyncio.Queue(),
            'user_name': user_name
        }
        self.players[player_id].update({"send_task": self._create_send_task(self.players[player_id], player_id),
                                        "receive_task": self._create_receive_task(self.players[player_id], player_id)})
        return self.players[player_id]['send_task'], self.players[player_id]['receive_task']


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
                    await self.redis_connection.xadd(self._room_id,json.loads(event),id='*',maxlen=50)
            except asyncio.CancelledError:
                raise

        return asyncio.create_task(task_fnc(player=player, player_id=player_id))


    def disconnect(self, player_id):
        self.players.pop(player_id)

    async def set_pubsub(self):
        if not self.pubsub.subscribed:
            await self.pubsub.subscribe(self._room_id)

class Broker():
    def __init__(self,game):
        self.game = game
        self.last_event_id = 0

    async def publish(self,event,to_whom):
        # to_whon like ('broadcas',_),('group',['123dafa','fasd123']),('user','213dasd')
        key , value = to_whom
        if key == 'broadcast':
            for key in self.game.players.keys():
                await self.game.players[key]['send_que'].put(event)
        elif key == 'group':
            for user_id in value:
                await self.game.players[user_id]['send_que'].put(event)
        elif key == 'user':
            await self.game.players[value]['send_que'].put(event)

    async def get_message(self):
        raw_message = await self.game.redis_connection.xread({self.game._room_id:self.last_event_id},block=12000000)
        if raw_message:
            message = parse_redis_stream_event(raw_message)
            return message
        return None

class Events():
    def __init__(self,game):
        self.game = game