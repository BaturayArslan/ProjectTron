from flask_wtf import FlaskForm
from wtforms import (StringField, PasswordField, validators, IntegerField)


class RegistrationForm(FlaskForm):
    class Meta:
        csrf = False

    email = StringField(
        'email', [validators.Email("Email must be valid."), validators.DataRequired("Please Enter email.")])
    username = StringField(
        'username', [validators.DataRequired("Please Enter Username"),
                     validators.Length(min=2, max=25, message="min must be 2,max must be 25")])
    avatar = IntegerField('avatar', [validators.DataRequired("Please enter avatar value"),
                                     validators.NumberRange(min=0, max=5, message="min must be 0,max must be 5")])
    password = PasswordField('password', [
        validators.DataRequired("Please Enter password."),
        validators.EqualTo('confirm', message="Passwords must match.")
    ])
    confirm = PasswordField('confirm')


class LoginForm(FlaskForm):
    class Meta:
        csrf = False

    email = StringField('email', [validators.DataRequired(message='Please Enter email')])
    password = PasswordField('password', [validators.DataRequired('Please enter a password'),
                                          validators.Length(min=1, max=25, message="min 8 max 25")])

class CompleteLoginForm(FlaskForm):
    class Meta:
        csrf = False

    username = StringField(
        'username', [validators.DataRequired("Please Enter Username"),
                     validators.Length(min=2, max=25, message="min must be 2,max must be 25")])
    avatar = IntegerField('avatar', [validators.DataRequired("Please enter avatar value"),
                                     validators.NumberRange(min=0, max=5, message="min must be 0,max must be 5")])