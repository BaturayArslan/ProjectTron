from drawProject import db
import pytest

@pytest.mark.parametrize("data,headers,path,expected", [
    (
            {
                "email": "test@test.com",
                "username": "test",
                "password": "test",
                "avatar": 0,
                "confirm": "test",
            },
            {
                "X-Forwarded-For": '94.123.218.184'
            },
            "/auth/register",
            201

    ),
    (
            {
                "email": "test@test.com",
                "username": "test",
                "password": "test",
                "avatar": 0,
                "confirm": "test",
                "hello": "world"
            },
            {
                "X-Forwarded-For": '94.123.218.184'
            },
            "/auth/register",
            301

    ),
    (
            {
                "email": "test@test.com",
                "username": "test",
                "password": "test",
                "avatar": 0,
                "confirm": "test",
            },
            None,
            "/auth/register",
            301
    )
])
def test_register(client, data, headers, path,expected):
    response = client.post(path, data=data, headers=headers)
    assert response.status_code == expected

# TODO :: write test for already registered user.