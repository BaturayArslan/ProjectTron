import email
from flask_wtf import FlaskForm
from wtforms import (StringField, PasswordField, validators)


class RegistrationForm(FlaskForm):
    email = StringField(
        'email', [validators.Email("Email must be valid."), validators.DataRequired()])
    name = StringField(
        'name', [validators.DataRequired(), validators.Length(min=5, max=25)])
    last_name = StringField(
        'last_name', [validators.DataRequired(), validators.Length(min=5, max=25)])
    password = PasswordField('password', [
        validators.DataRequired("Please Enter password."),
        validators.EqualTo('confirm', message="Passwords must match.")
    ])
    confirm = PasswordField('confirm')
