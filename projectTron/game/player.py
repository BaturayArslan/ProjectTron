import math
from projectTron.utils.utils import bezier

class User:
    def __init__(self, event):
        """ event = {
            'event_number': 1,
            'info': {
                'user_id': user_id,
                'user_name': user_name,
                'win_round': 0,
                'color': 1,
                'is_ready': False,
                'avatar': player_info['avatar']
            },
            'timestamp': datetime.timestamp(datetime.utcnow())
        }"""

        self.user_id = event['info']['user_id']
        self.user_name = event['info']['user_name']
        self.color = event['info']['color']
        self.win_round = event['info']['win_round']
        self.is_ready = event['info']['is_ready']
        self.join_time = event['timestamp']
        self.avatar = event['info']['avatar']
        self.position_points = []


class Player(User):
    def __init__(self, game, event):
        User.__init__(self, event)
        self.game = game
        self.width = 50
        self.height = 20
        self.x = 0
        self.y = 0
        self.rotationAngle = 0
        self.speed = 0
        self.maxSpeed = 5
        self.deltaX = 0
        self.deltaY = 0
        self.renderTile = True
        self.tiles = []
        self.keys = {'w': 0, 'a': 0, 's': 0, 'd': 0}

    async def update(self, deltaTime):
        if(self.keys['w'] != 0 and self.speed <= self.maxSpeed):
            self.keys['w'] += deltaTime
            if(self.keys['w'] > 2000):
                self.keys['w'] = 2000
            t = (1/2000) * self.keys['w']
            self.speed += bezier(
                    t,
                    { "x": 0, "y": 0 },
                    { "x": 0, "y": 0 },
                    { "x": 0, "y": 1 },
                    { "x": 1, "y": 1 }
                )['y'] / 12
        elif(self.keys['s'] != 0 and self.speed > 0):
            self.keys['s'] += deltaTime
            t = (1/1000) * self.keys['s']
            self.speed -= bezier(
                    t,
                    { "x": 0, "y": 1 },
                    { "x": 0, "y": 1 },
                    { "x": 0, "y": 0 },
                    { "x": 1, "y": 0 }
                )['y'] / 5
            if(self.speed < 0 ):
                self.speed = 0
        else:
            self.speed = max(0,self.speed - 3/1000)

        if(self.keys['a'] != 0):
            self.rotationAngle -= 4
        elif(self.keys['d'] != 0):
            self.rotationAngle += 4

        await self.calculateTrace()


        for tile in self.tiles:
            tile.update(deltaTime)

        self.tiles = [tile for tile in self.tiles if not tile.isGonnaDelete]
        self.x += self.speed * math.cos((math.pi / 180) * self.rotationAngle)
        self.y += self.speed * math.sin((math.pi / 180) * self.rotationAngle)


    async def calculateTrace(self):
        self.deltaX += abs(self.speed * math.cos((math.pi/180) * self.rotationAngle))
        self.deltaY += abs(self.speed * math.sin((math.pi/180) * self.rotationAngle))
        distance = math.sqrt(self.deltaX**2 + self.deltaY**2)
        if (distance > Tile.DISTANCE_BETWEEN and self.renderTile):
            x = math.cos(math.pi + (math.pi / 180) * self.rotationAngle) * (self.width / 2) + (self.x + self.width / 2)
            y = math.sin(math.pi + (math.pi / 180) * self.rotationAngle) * (self.width / 2) + (self.y + self.height / 2)

            self.tiles.append(Tile(self,x,y,self.color))

            # Detect if this tile cause any collision
            if(len(self.tiles) > 1):
                await self.game.board.collision_detect({'x':x,'y':y,'rotation':self.rotationAngle},
                                                 	   {'x':self.tiles[-2].x,'y':self.tiles[-2].y,'rotation':self.rotationAngle},
                                                 	   self.color)

            self.deltaX = 0
            self.deltaY = 0

    def set_start_position(self, x, y, rotationAngle):
        self.x = x
        self.y = y
        self.rotationAngle = rotationAngle
        self.start_x = x
        self.start_y = y
        self.start_rotationAngle = rotationAngle

    def reset(self):
        self.x = self.start_x
        self.y = self.start_y
        self.rotationAngle = self.start_rotationAngle
        self.speed = 0
        self.deltaX = 0
        self.deltaY = 0
        self.renderTile = True
        self.tiles = []
        self.is_ready = False

    def transform_to_dict(self):
        return {
            'x': self.x,
            'y': self.y,
            'rotationAngle': self.rotationAngle,
            'speed': self.speed,
            'renderTile': self.renderTile,
            'user_id': self.user_id,
            'user_name': self.user_name,
            'maxSpeed':self.maxSpeed,
            'color': self.color,
            'win_round': self.win_round,
            'join_time': self.join_time,
            'is_ready': self.is_ready,
            'avatar': self.avatar,
            'height':self.height,
            'width':self.width,
            'tiles':[tile.transform_to_dict() for tile in self.tiles]
        }

class Tile:
    TILE_WIDTH = 8
    DISTANCE_BETWEEN = 16

    def __init__(self,player,x,y,color):
        self.player = player
        self.x = x
        self.y = y
        self.color = color
        self.lifeTime = 0
        self.maxLifeTime = 3500
        self.isGonnaDelete = False

    def update(self,deltaTime):
        if (self.lifeTime > self.maxLifeTime and len(self.player.tiles) > 1):
            self.player.game.board.clear_trace({'x':self.x,'y':self.y},
                                               {'x':self.player.tiles[1].x,'y':self.player.tiles[1].y})
            self.isGonnaDelete = True
        else:
            self.lifeTime += deltaTime

    def transform_to_dict(self):
        return {
            'x':self.x,
            'y':self.y,
            'color':self.color,
        }