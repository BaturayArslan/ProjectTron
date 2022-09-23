import aioredis
import asyncio
import async_timeout
import json
from datetime import datetime
from quart import g, current_app
from werkzeug.local import LocalProxy
from enum import Enum


async def get_redis():
    if ("redis_pubsub" or "redis_connection") not in g:
        connection = await aioredis.from_url('redis://ec2-3-250-153-214.eu-west-1.compute.amazonaws.com', port=6379,
                                             username='default', password=current_app.config['REDIS'])
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
        print('hello world', flush=True)
        try:
            pubsub = g.redis_rooms_pubsub
            while True:
                print('hello world',flush=True)
                async with async_timeout.timeout(10):
                    raw_message = await pubsub.get_message(ignore_subscribe_messages=True)
                    if raw_message:
                        message = json.loads(raw_message['data'])
                        self.events.append((message, datetime.timestamp(datetime.utcnow())))
                        self.check_event()

                        task = asyncio.create_task(self.publish(message))
                        await self.subs.join()
                await asyncio.sleep(1)
        except Exception as e:
            raise e
        except asyncio.TimeoutError as e:
            raise e

    async def publish(self, message):
        try:
            while True:
                sub = self.subs.get_nowait()
                await sub.put(message)
                self.subs.task_done()
        except Exception as e:
            pass

    async def subscribe(self):
        try:
            channel = asyncio.Queue()
            print('4')
            await self.subs.put(channel)
            message = await asyncio.wait_for(channel.get(),5)
            return message
        finally:
            pass

    def get_events(self):
        events_len = len(self.events)
        mod = events_len % 100
        quotient = events_len // 100
        if quotient == 0:
            new_arr = self.events[0:]
        else:
            new_arr = self.events[mod::]
        return new_arr

    def check_event(self):
        if len(self.events) > 200:
            self.events = self.events[100:]

    def syncronize(self, time_stamp):
        for index, item in enumerate(self.events):
            if time_stamp == item[1]:
                return self.events[index + 1:]
        return None


broker = LocalProxy(Broker)


class Events():
    ROOM_CREATION = None
    USER_JOIN = None
    USER_LEAVES = None

    def set_room_creation(self, room_id, data, user_id):
        self.ROOM_CREATION = {
            'event': 'room creation',
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
            }
        }

    def set_user_join(self,room_id):
        self.USER_JOIN = {
            'event': 'user join',
            'room_id': str(room_id)
        }

    def set_user_laeves(self, room_id):
        self.USER_LEAVES = {
            'event': 'user leaves',
            'room_id': str(room_id)
        }
events = Events()