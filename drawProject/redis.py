import aioredis
from quart import g , current_app
from werkzeug.local import LocalProxy

async def get_redis():
    if ("redis_pubsub" or "redis_connection") not in g:
        connection = await aioredis.from_url('redis://ec2-3-250-153-214.eu-west-1.compute.amazonaws.com',port=6379,poolsize=50)
        pubsub:aioredis.client.PubSub = connection.pubsub()
        await pubsub.subscribe('rooms_info_feed')
        g.redis_rooms_pubsub = pubsub
        g.redis_connection = connection
    return g.redis_rooms_pubsub,g.redis_connection


redis = LocalProxy(get_redis)