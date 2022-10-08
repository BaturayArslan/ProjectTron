import asyncio
import json
import pytest
import pytest_asyncio
from quart import current_app
from flask_jwt_extended import decode_token

from drawProject import redis,db
from drawProject.utils.utils import parse_redis_stream_event

@pytest_asyncio.fixture()
async def get_sockets(class_app,class_client,get_user,get_room):
    app = class_app
    client = class_client
    user1, user2 = get_user
    room_id = get_room
    async with app.app_context():
        user1_token = decode_token(user1['auth_token'])
        user2_token = decode_token(user2['auth_token'])

        headers1 = {
            'Authorization': f'Bearer {user1["auth_token"]}'
        }
        headers2 = {
            'Authorization': f'Bearer {user2["auth_token"]}'
        }

        socket1 = client.websocket(f'/ws/room/{room_id}', headers=headers1)
        socket2 = client.websocket(f'/ws/room/{room_id}', headers=headers2)

        yield socket1,socket2

        await socket1.disconnect()
        await socket2.disconnect()

@pytest.mark.usefixtures('login_user_fixture')
@pytest.mark.asyncio
class TestGame:
    async def test_game_broker(self,class_app,class_client,get_user,get_room):
        app = class_app
        client = class_client
        user1, user2 = get_user
        room_id = get_room
        async with app.app_context():
            user1_token = decode_token(user1['auth_token'])
            user2_token = decode_token(user2['auth_token'])
            _,redis_connection = await redis.get_redis()

            headers1 = {
                'Authorization': f'Bearer {user1["auth_token"]}'
            }
            headers2 = {
                'Authorization': f'Bearer {user2["auth_token"]}'
            }
            packet1,packet2= await self.get_tasks(client,headers1,headers2,room_id)
            await asyncio.sleep(2)

            # First event recevied from socket must be user_join and system_message.
            # The user that first join room gonna receive user_join and system_message event twice.One for himself one for user2
            socket1_received_events=[]
            socket2_received_events=[]
            for i in range(4):
                try:
                    if i % 2 == 0:
                        event = packet1[1].get_nowait()
                        socket1_received_events.extend(event)
                    else:
                        event = packet2[1].get_nowait()
                        socket2_received_events.extend(event)
                except asyncio.QueueEmpty:
                    continue
            assert socket1_received_events[0]['event_number'] == 1
            assert socket2_received_events[0]['event_number'] == 1

            # Test game.broker.publish function
            await app.games[room_id].broker.publish({'event_number':16,'hello':'world'},('broadcast',None))
            event1 = await packet1[1].get()
            event2 = await packet2[1].get()
            assert event1['event_number'] == 16 and event2['event_number'] == 16

            # Test game.broker.push_event function (event id must be great or equal than last event id ,last event id was timestamp so id must be very high interger value )
            await app.games[room_id].broker.push_event({'event_number':16,'hello':'world'},id=9000000000000)
            redis_event = await redis_connection.xread({room_id:8999999999999},block=1200)
            parsed_redis_event = parse_redis_stream_event(redis_event)
            assert parsed_redis_event[0]['event_number'] == 16

            #Test game.broker.get_event (get_event written for get events that has higher id  than last_event_id,last_event_id updated after each get_events call)
            await app.games[room_id].broker.push_event({'event_number': 16, 'hello': 'world'})
            events = await app.games[room_id].broker.get_events()
            assert app.games[room_id].broker.last_event_id == '9000000000000-1'

            #await asyncio.gather(packet1[0],packet2[0])





    async def get_tasks(self,client,headers1,headers2,room_id):
        receive_que1, send_que1, receive_que2, send_que2 = self.create_ques(4)
        socket1 = client.websocket(f'/ws/room/{room_id}', headers=headers1)
        socket2 = client.websocket(f'/ws/room/{room_id}', headers=headers2)
        task1 = asyncio.create_task(self.socket_tasks(socket1, receive_que1, send_que1))
        task2 = asyncio.create_task(self.socket_tasks(socket2, receive_que2, send_que2))
        return [(task1,receive_que1,send_que1),(task2,receive_que2,send_que2)]


    async def socket_tasks(self,socket,receive_que,send_que):
        async with socket as socket:
            receive_task = asyncio.create_task(self.recevie_task(socket,receive_que))
            send_task = asyncio.create_task(self.send_task(socket,send_que))
            await asyncio.gather(receive_task,send_task)

    async def recevie_task(self,socket,receive_que):
        try:
            while True:
                data = await socket.receive()
                event = json.loads(data)
                await receive_que.put(event)
        except asyncio.CancelledError:
            await socket.disconnect()

    async def send_task(self,socket,send_que):
        try:
            while True:
                event = await send_que.get()
                data = json.dumps(event)
                await socket.send(data)
        except asyncio.CancelledError:
            await socket.disconnect()

    def create_ques(self,count):
        ques = []
        for i in range(count):
            ques.append(asyncio.Queue())
        return ques