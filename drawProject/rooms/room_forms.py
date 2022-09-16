from flask_wtf import FlaskForm
from wtforms import (StringField,IntegerField,validators,HiddenField)

class CreateRoomForm(FlaskForm):
    class Meta:
        csrf = False

    max_user = IntegerField("max_user",[validators.DataRequired('Please Try Again.'),validators.NumberRange(min=5,max=15,message='Please Try Again.')])
    max_point = IntegerField('max_point',[validators.DataRequired('Please Try Again.'),validators.NumberRange(min=80,max=200,message='Please Try Again')])
    admin = HiddenField('admin',[validators.DataRequired('Please Try Again.')])
    password = StringField('password')
