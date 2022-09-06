import os
from pathlib import Path
from dotenv import load_dotenv
from datetime import timedelta

PROJECT_DIR = Path(__file__).parent
load_dotenv(PROJECT_DIR / '.env')


class BaseConfig:
    SECRET_KEY = os.environ.get('SECRET_KEY')
    MONGO_URI = os.environ.get('MONGO_URI')
    DEBUG = False
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=5)


class DevConfig(BaseConfig):
    DEBUG = True
