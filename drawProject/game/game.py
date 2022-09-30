import asyncio

class Game:
    def __init__(self):
        self.players = {}

    def register(self,player_id,websocket):
        self.players[player_id] = {
            'connection' : websocket,
            'send_que': asyncio.Queue(),
            'recieve_que': asyncio.Queue(),
        }

    def _create_send_task(self,player):
        def task_fnc():
            while True:
                try:
                    event = await player['send_que'].get()
                    await player['websocket'].send(event)
                except asyncio.CancelledError:
                    raise
