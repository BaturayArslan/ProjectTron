from quart.scaffold import HTTPException
from quart import jsonify
import traceback

async def dberror_handler(e):
    return jsonify(e.to_dict()),e.status_code

async def duplicate_key_handler(e):
    return jsonify({'message':"This email already registered.Please try another email.",'details':e.details}),202

async def bad_request_handler(e):
    return jsonify({"message": f"{str(e)}"}), 400

async def exception_handler(e):
    print(traceback.format_exc())
    return jsonify({"message":repr(type(e)) + str(e)}),500

async def asyncio_timeout_handler(e):
    return jsonify({"message":f"timeout {str(e)}."}),500

async def checkfailed_handler(e):
    return jsonify({"message": f"{str(e)}"}), 200
