from wsgiref.validate import validator
from flask_wtf import FlaskForm
from wtforms import (StringField,IntegerField,validators,HiddenField)

class CreateRoomForm(FlaskForm):
    class Meta:
        csrf = False

    name = StringField('name',[validators.DataRequired('Please Enter name'),validators.Length(min=5,max=25,message='name must be min 5,max 25')])
    max_user = IntegerField("max_user",[validators.DataRequired('Please Try Again.'),validators.NumberRange(min=2,max=15,message='Please Try Again.')])
    max_point = IntegerField('max_point',[validators.DataRequired('Please Try Again.'),validators.NumberRange(min=5,max=20,message='Please Try Again')])
    password = StringField('password')
