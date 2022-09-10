import pytest


def test_login(client):
    data = {
        'email': 'test@test.com',
        'password': 'test'
    }
    response = client.post("/auth/login",data=data)