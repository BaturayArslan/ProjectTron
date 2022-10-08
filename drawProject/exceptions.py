class DbError(Exception):
    pass


class BadRequest(Exception):
    pass

class RoomCreationFailed(Exception):
    pass

class UserJoinRoomFailed(Exception):
    pass

class CheckFailed(Exception):
    pass