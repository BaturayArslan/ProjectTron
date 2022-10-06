import pytest
import pytest_asyncio
import asyncio
from drawProject.factory import create_app

@pytest_asyncio.fixture()
def test_app():
    return create_app(test=True)

# @pytest_asyncio.fixture()
# def app():
#     app = create_app(test=True)
#     return app
#
# @pytest_asyncio.fixture()
# def client(app):
#     return app.test_client()

@pytest_asyncio.fixture(scope="class")
def class_app():
    app =  create_app(test=True)
    return app

@pytest_asyncio.fixture(scope="class")
def class_client(class_app):
    return class_app.test_client()

@pytest_asyncio.fixture(scope="class")
def event_loop():
    loop = asyncio.get_event_loop_policy().get_event_loop()
    yield loop
    for task in asyncio.all_tasks(asyncio.get_event_loop_policy().get_event_loop()):
        if task.get_name() == 'background_task':
            task.cancel()
            asyncio.get_event_loop().run_until_complete(task)

    loop.close()


@pytest.fixture()
def runner(app):
    return app.test_cli_runner()

