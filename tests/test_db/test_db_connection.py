import aioredis.client
import pytest
import pytest_asyncio
import pdb

from projectTron import db
from projectTron import redis


@pytest.mark.asyncio
async def test_get_db(test_app):
    # Trigger app.before_first_request function
    await test_app.test_client().get('/')

    async with test_app.test_request_context('/',method="GET"):
        test_db = db.get_db()
        assert test_db is not None
        assert test_db.name == 'draw_test'
        assert test_db.client.options._options['maxPoolSize'] == 10
        assert test_db.client.options._options['connectTimeoutMS'] == 5.0
        assert test_db.client.options._options['wTimeoutMS'] == 5000

        # TODO :: test if you can read and write to database

@pytest.mark.asyncio
async def test_get_redis(test_app):
    # Trigger app.before_first_request function
    await test_app.test_client().get('/')

    async with test_app.test_request_context('/',method="GET"):
        redis_rooms_pubsub , redis_connection = await redis.get_redis()
        assert await redis_connection.execute_command('PING')
        assert isinstance(redis_connection,aioredis.client.Redis)
        assert isinstance(redis_rooms_pubsub,aioredis.client.PubSub)


