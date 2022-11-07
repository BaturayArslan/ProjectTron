from projectTron.factory import  create_app
from hypercorn.config import Config
from hypercorn.asyncio import serve
import asyncio

config = Config()
config.bind = ["localhost:5000"]

if __name__ == '__main__':
    app = create_app(test=True)
    # asyncio.run(serve(app,config))
    app.run(host="0.0.0.0")
