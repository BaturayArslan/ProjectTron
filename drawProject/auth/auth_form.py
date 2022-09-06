from flask_wtf import FlaskForm
from wtforms import (StringField, PasswordField, validators,IntegerField)


class RegistrationForm(FlaskForm):
    class Meta:
        csrf = False

    email = StringField(
        'email', [validators.Email("Email must be valid."), validators.DataRequired()])
    username = StringField(
        'username', [validators.DataRequired(), validators.Length(min=2, max=25)])
    avatar = IntegerField('avatar')
    password = PasswordField('password', [
        validators.DataRequired("Please Enter password."),
        validators.EqualTo('confirm', message="Passwords must match.")
    ])
    confirm = PasswordField('confirm')


class LoginForm(FlaskForm):
    class Meta:
        csrf = False

    username = StringField('username', [validators.DataRequired(message='Please Enter Username'),
                                    validators.Length(min=5, max=25, message="min 5 max 25")])
    password = PasswordField('password', [validators.DataRequired('Please enter a password'),
                                          validators.Length(min=8, max=25, message="min 8 max 25")])
