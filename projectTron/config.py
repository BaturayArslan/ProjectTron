import os
from pathlib import Path
from dotenv import load_dotenv,find_dotenv
from datetime import timedelta
import pdb

PROJECT_DIR = Path(__file__).parents[1]
ENV_FILE = PROJECT_DIR / '.env'

load_dotenv(find_dotenv(str(ENV_FILE),raise_error_if_not_found=True))


class BaseConfig:
    SECRET_KEY = os.getenv('SECRET_KEY')
    MONGO_URI = os.getenv('MONGO_URI')
    DEBUG = False
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=120)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=1)
    JWT_TOKEN_LOCATION = ['headers']

class DevConfig(BaseConfig):
    DEBUG = True
    DATABASE_NAME = "draw_dev"

class TestConfig(BaseConfig):
    DEBUG = False
    TESTING = True
    DATABASE_NAME = 'draw_test'
    JWT_SECRET_KEY = 'safira'
    #SERVER_NAME= 'draw.hbarslan.com'
    FACEBOOK_CONSUMER_KEY= os.getenv('FACEBOOK_CONSUMER_KEY')
    FACEBOOK_CONSUMER_SECRET= os.getenv('FACEBOOK_CONSUMER_SECRET')
    REDIS_URL = 'redis://ec2-3-250-153-214.eu-west-1.compute.amazonaws.com'
    REDIS_PASSWORD = os.getenv('REDIS')
