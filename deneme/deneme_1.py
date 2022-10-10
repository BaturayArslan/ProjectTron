import asyncio
import aioredis
import pprint
import json
import async_timeout
import  async_timeout
from projectTron.utils.utils import parse_redis_stream_event

async def hello():
    connection = await aioredis.from_url('redis://ec2-3-250-153-214.eu-west-1.compute.amazonaws.com',port=6379,username='default', password='431lfmdsfj13e1mdeqw!Fq@Hdf')
    events = await connection.xread({'63347ca13c7f49da780958d1':0},count=3,block=120)
    return events

# events=asyncio.run(hello())
# parsed = parse_redis_stream_event(events)
# pprint.pprint(parsed)
# pprint.pprint(events)

class Deneme:
    def say_hello(self):
        if hasattr(self,'say_goodbye'):
            print('True')
            getattr(self,'say_goodbye')()
        else:
            print("false")

    def say_goodbye(self):
        print('good bye.')

deneme = Deneme()
deneme.say_hello()