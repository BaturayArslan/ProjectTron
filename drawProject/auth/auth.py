from aifc import Error
from crypt import methods
from flask import Blueprint, request, g, redirect, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from .auth_form import RegistrationForm
from ..db import get_db

bp = Blueprint("auth", __name__, url_prefix='/auth')


@bp.route("/register", methods=("POST"))
def register():
    form_data = RegistrationForm(request.form)
    db = get_db()
    try:
        if form_data.validate():
            data = request.form.to_dict()
            data['password'] = generate_password_hash(data['password'])
            try:
                db.users.insert_one(data)
                return redirect(url_for('auth.login'))
            except Exception:
                return {
                    "erorr": "erorr occured when registering users to database.",
                    "message": f"{Exception.args}"
                }
    except Exception:
        return {
            "error": "error occured when registering user.",
            "message": f"{form_data.errors}"

        }
