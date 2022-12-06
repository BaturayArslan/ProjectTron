import json
import math
from bson import ObjectId
from collections.abc import Iterable
import decimal

def string_to_int(obj:dict):
    for key in obj.keys():
        try:
            obj[key] = int(obj[key])
        except ValueError as e :
            continue
    return obj

def objectid_to_str(obj:Iterable):
    if isinstance(obj,str):
        return obj

    if isinstance(obj,dict):
        for key in obj.keys():
            if isinstance(obj[key],ObjectId):
               obj[key] = str(obj[key])
            if isinstance(obj[key],Iterable):
                obj[key] = objectid_to_str(obj[key])
    else:
        for index,item in enumerate(obj):
            if isinstance(item, ObjectId):
                obj[index] = str(item)
            if isinstance(item,Iterable):
                obj[index] = objectid_to_str(item)
    return obj

def normal_to_redis_timestamp(timestamp:float):
    after_comma = '{:.2f}'.format(timestamp % 1).split('.')[1]
    before_comma = str(int(timestamp))
    redis_timestamp = before_comma + after_comma
    return int(redis_timestamp)

def redis_to_normal_timestamp(timestamp:int):
    digits = decimal.Decimal(timestamp).as_tuple()
    last_two_digit = digits.digits[-2:]
    str_last_two_digits = '%d%d'%last_two_digit
    other_digits = digits.digits[:-2]
    str_other_digits = ''.join(map(str,other_digits))
    return float(str_other_digits + "." + str_last_two_digits)

def parse_redis_stream_event(events):
    """
        events :
                [[b'63347ca13c7f49da780958d1',
                 [(b'166437336747-0',
                  {b'container':{
                    b'msg': b'merhaba',
                    b'name': b'message sends',
                    b'reciever': b'63347ca13c7f49da780958d1',
                    b'sender': b'63347ca13c7f49da780958d0',
                    b'timestamp': b'1664373367.466694'}
                  }),
                (b'1664662371870-0', {b'hello': b'word', b'id': b'1664662371870-0'})]]]
        return :
                [{'id': '166437336747-0',
                  'msg': 'merhaba',
                  'name': 'message sends',
                  'reciever': '63347ca13c7f49da780958d1',
  '               'sender': '63347ca13c7f49da780958d0',
                  'timestamp': '1664373367.466694'},
                {'hello': 'word', 'id': '1664662371870-0'}]

    """
    result = []
    for event in events[0][1]:
        id = event[0]
        parsed_event = json.loads(event[1][b'container'])
        result.append(parsed_event)
    return result

def bezier(t,p0,p1,p2,p3):
    cX = 3 * (p1['x'] - p0['x'])
    bX = 3 * (p2['x'] - p1['x']) - cX
    aX = p3['x'] - p0['x'] - cX - bX

    cY = 3 * (p1['y'] - p0['y'])
    bY = 3 * (p2['y'] - p1['y']) - cY
    aY = p3['y'] - p0['y'] - cY - bY

    x = aX * math.pow(t, 3) + bX * math.pow(t, 2) + cX * t + p0['x']
    y = aY * math.pow(t, 3) + bY * math.pow(t, 2) + cY * t + p0['y']

    return {'x':x,'y':y}