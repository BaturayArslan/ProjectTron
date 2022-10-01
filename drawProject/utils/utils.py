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
    result = []
    for event in events[0][1]:
        id = event[0]
        event[1].update({"id":id})
        result.append(event[1])
    return result