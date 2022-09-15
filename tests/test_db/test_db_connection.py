import pytest
import pytest_asyncio
import pdb

from drawProject import db


@pytest.mark.asyncio
async def test_get_db(test_app):
    async with test_app.test_request_context('/',method="GET"):
        test_db = db.get_db()
        assert test_db is not None
        assert test_db.name == 'draw_test'
        assert test_db.client.options._options['maxPoolSize'] == 100
        assert test_db.client.options._options['connectTimeoutMS'] == 5.0
        assert test_db.client.options._options['wTimeoutMS'] == 5000

        # TODO :: test if you can read and write to database
