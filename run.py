from projectTron.factory import create_app
from hypercorn.config import Config
from hypercorn.asyncio import serve
import asyncio


#if __name__ == '__main__':
app = create_app(test=True)
app.run()
