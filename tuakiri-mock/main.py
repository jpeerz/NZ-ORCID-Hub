# -*- coding: utf-8 -*-
"""Application module gluing script.

Simple solution to overcome circular import problem:
http://charlesleifer.com/blog/structuring-flask-apps-a-how-to-for-those-coming-from-django/
"""

import logging
import os

from flask import Flask, redirect, render_template, url_for, flash, request
from flask_admin import Admin
from flask_debugtoolbar import DebugToolbarExtension
from collections import namedtuple
from flask_wtf import FlaskForm
from wtforms import TextField, PasswordField, validators
from flask_login import login_user, LoginManager, UserMixin, login_required, current_user, logout_user


class User(UserMixin):
    id = None
    email = None
    name = None

users = dict()

app = Flask(__name__)
app.config.from_object(__name__)
login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)


@login_manager.user_loader
def load_user(email):
    return users.get(email, None)

# @login_manager.request_loader
# def request_loader(request):
#     email = request.form.get("email")

#     user = User()
#     user.id = email

#     if email not in users:
#         users[email] = user

#     return user

class LoginForm(FlaskForm):
    username = TextField("Username", [validators.Required(), validators.Length(min=4, max=25)])
    password = PasswordField("Password", [validators.Required(), validators.Length(min=6, max=200)])

@app.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = form.username.data
        print("****", email)
        user = users.get(email)
        if not user:
            user = User(email)
            users[email] = user
        login_user(user)
        flash("Logged in successfully.", "info")
        next = request.args.get("next")
        return redirect(next or url_for("index"))
    return render_template("login.html", form=form)

@app.route('/logout')
def logout():
    logout_user()
    return 'Logged out'

@app.route("/")
@login_required
def index():
    return f"BINGO! {current_user}"

@app.route("/ds/DS")
def ds():
    return render_template("home_organisation.html")


if __name__ == "__main__":
    app.debug = True
    app.secret_key = os.urandom(24)
    app.run(debug=True, port=8989)
