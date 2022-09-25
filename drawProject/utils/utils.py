from bson import ObjectId
from collections.abc import Iterable
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