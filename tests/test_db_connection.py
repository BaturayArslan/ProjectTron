import pytest
import pdb

from drawProject import db



def test_get_db(test_app):
    with test_app.test_request_context('/'):
        test_db = db.get_db()
        assert test_db is not None
        assert test_db.name == 'draw_test'
        assert test_db.client.options._options['maxPoolSize'] == 100
        assert test_db.client.options._options['connectTimeoutMS'] == 5.0
        assert test_db.client.options._options['wTimeoutMS'] == 5000

