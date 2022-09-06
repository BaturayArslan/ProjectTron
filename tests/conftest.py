import pytest
from drawProject.factory import create_app

@pytest.fixture
def test_app():
    return create_app(test=True)

@pytest.fixture
def app():
    app = create_app(test=True)
    return app

@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def runner(app):
    return app.test_cli_runner()