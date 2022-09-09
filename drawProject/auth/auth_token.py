import jwt
import datetime
from flask import current_app


def encode_auth_token(user_data):
    try:
        payload = {
            'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=5),
            'iat': datetime.datetime.utcnow(),
            'sub': user_data['email']
        }
        return jwt.encode(payload, current_app.config.get('SECRET_KEY'), algorithm='HS256')
    except Exception as e:
        return {
            "erorr": "Error occured while token generation.",
            "message": f"{repr(e)}"
        }

def decode_auth_token(token):
    try:
        payload = jwt.decode(token,current_app.config.get('SECRET_KEY'))
        return payload['sub']
    except jwt.ExpiredSignatureError:
        return 'Signature expired.'
    except jwt.InvalidTokenError:
        return False