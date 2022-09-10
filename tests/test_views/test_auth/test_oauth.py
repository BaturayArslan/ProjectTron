import pytest

def test_redirect_authorization(client):
    client.get('/oauth/')