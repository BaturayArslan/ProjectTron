

def string_to_int(obj:dict):
    for key in obj.keys():
        try:
            obj[key] = int(obj[key])
        except ValueError as e :
            continue
    return obj