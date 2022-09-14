import pytest
from drawProject.factory import create_app

@pytest.fixture
def test_app():
    return create_app(test=True)

@pytest.fixture()
def app():
    app = create_app(test=True)
    return app

@pytest.fixture()
def client(app):
    return app.test_client()

@pytest.fixture(scope="class")
def class_app():
    app = create_app(test=True)
    return app

@pytest.fixture(scope="class")
def class_client(class_app):
    return class_app.test_client()


@pytest.fixture()
def runner(app):
    return app.test_cli_runner()

