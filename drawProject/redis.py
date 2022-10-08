import aioredis
import asyncio
import async_timeout
import json
from datetime import datetime
from quart import g, current_app
from werkzeug.local import LocalProxy
from enum import Enum


async def get_redis():
    if ("redis_rooms_pubsub" or "redis_connection") not in g:
        connection = current_app.redis_connection_pool
        pubsub: aioredis.client.PubSub = connection.pubsub()
        await pubsub.subscribe('rooms_info_feed')
        g.redis_rooms_pubsub = pubsub
        g.redis_connection = connection
    return g.redis_rooms_pubsub, g.redis_connection


redis = LocalProxy(get_redis)


class Broker:
    subs = asyncio.Queue()
    events = list()

    async def listen(self):
        try:
            pubsub = g.redis_rooms_pubsub
            while True:
                async with async_timeout.timeout(10):
                    raw_message = await pubsub.get_message(ignore_subscribe_messages=True)
                    if raw_message:
                        message = json.loads(raw_message['data'])
                        self.events.append(message)
                        print(message)
                        self.check_events()
                        current_app.publish_task = asyncio.create_task(self.publish(message))
                        await self.subs.join()
                await asyncio.sleep(0.1)
        except asyncio.CancelledError as e:
            print('Listen task cancelled.')
            await current_app.publish_task
        except Exception as e:
            #Rerun if any error occurs.
            current_app.add_background_task(self.listen)
            print('Something went wrong on broker.listen')


    async def publish(self, message):
        try:
            while True:
                sub = self.subs.get_nowait()
                await sub.put(message)
                self.subs.task_done()
        except Exception as e:
            pass

    async def subscribe(self):
        channel = asyncio.Queue()
        await self.subs.put(channel)
        print('subscribed.')
        message = await asyncio.wait_for(channel.get(),130)
        return message


    def get_events(self):
        events_len = len(self.events)
        mod = events_len % 100
        quotient = events_len // 100
        if quotient == 0:
            new_arr = self.events[0:]
        else:
            new_arr = self.events[mod::]
        return new_arr

    def check_events(self):
        if len(self.events) > 200:
            self.events = self.events[100:]

    def syncronize(self, time_stamp):
        for index, item in enumerate(self.events):
            if time_stamp == item['timestamp']:
                return self.events[index + 1:]
        return None


broker = LocalProxy(Broker)


class Events():
    ROOM_CREATION = None
    USER_JOIN = None
    USER_LEAVES = None
    MESSAGE_SENDS = None
    @staticmethod
    def set_room_creation(room_id, data, user_id):
        Events.ROOM_CREATION = {
            'name': 'room creation',
            'data': {
                '_id': str(room_id),
                'max_user': data['max_user'],
                'max_point': data['max_point'],
                "status": {
                    "public": data['status']['public']
                },
                'admin': str(data['admin']),
                'users': [
                    {
                        '_id': str(user_id),
                        'point': 0,
                        "color": 0,
                        'win_count': 0,
                        'kick_vote': 0,

                    }
                ]
            },
            'timestamp': datetime.timestamp(datetime.utcnow())
        }

    @staticmethod
    def set_user_join(room_id):
        Events.USER_JOIN = {
            'name': 'user join',
            'room_id': str(room_id),
            'timestamp': datetime.timestamp(datetime.utcnow())
        }

    @staticmethod
    def set_user_laeves(room_id):
        Events.USER_LEAVES = {
            'name': 'user leaves',
            'room_id': str(room_id),
            'timestamp': datetime.timestamp(datetime.utcnow())
        }
    @staticmethod
    def set_message_sends(user_id,msg,timestamp,friend_id):
        Events.MESSAGE_SENDS = {
            'name' : 'message sends',
            'sender': user_id,
            'reciever': friend_id,
            'msg':msg,
            'timestamp':timestamp
        }
events = Events()