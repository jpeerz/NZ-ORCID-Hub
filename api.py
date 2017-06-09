# -*- coding: utf-8 -*-
"""API views."""

import json
import os
from collections import namedtuple

from flask import (flash, redirect, render_template, request, send_from_directory, url_for)
from flask_admin.form import SecureForm

import swagger_client
from application import admin, app
from config import ORCID_BASE_URL, SCOPE_ACTIVITIES_UPDATE
from forms import BitmapMultipleValueField, RecordForm, OrgInfoForm
from login_provider import roles_required
from models import PartialDate as PD
from models import (OrcidToken, Organisation, OrgInfo, Role, User, UserOrgAffiliation)
# NB! Should be disabled in production
from pyinfo import info
from swagger_client.rest import ApiException
from application import app, oauth
from models import Client
from flask_login import current_user, login_required, login_user, logout_user
from datetime import datetime, timedelta


@oauth.clientgetter
def load_client(client_id):
    return Client.get(client_id=client_id)


@oauth.grantgetter
def load_grant(client_id, code):
    return Grant.get(client_id=client_id, code=code)

@oauth.grantsetter
def save_grant(client_id, code, request, *args, **kwargs):
    # decide the expires time yourself
    expires = datetime.utcnow() + timedelta(seconds=100)
    grant = Grant.create(
        client_id=client_id,
        code=code['code'],
        redirect_uri=request.redirect_uri,
        _scopes=' '.join(request.scopes),
        user=current_user,
        expires=expires
    )
    return grant


@oauth.tokengetter
def load_token(access_token=None, refresh_token=None):
    if access_token:
        return Token.get(access_token=access_token)
    elif refresh_token:
        return Token.get(refresh_token=refresh_token)



@oauth.tokensetter
def save_token(token, request, *args, **kwargs):
    toks = Token.select(Token.client_id == request.client.client_id & Token.user_id == request.user.id)
    # make sure that every client has only one token connected to a user
    for t in toks:
        t.delete()

    expires_in = token.get('expires_in')
    expires = datetime.utcnow() + timedelta(seconds=expires_in)

    tok = Token.create(
        access_token=token['access_token'],
        refresh_token=token['refresh_token'],
        token_type=token['token_type'],
        _scopes=token['scope'],
        expires=expires,
        client_id=request.client.client_id,
        user_id=request.user.id,
    )
    return tok


@app.route('/oauth/authorize', methods=['GET', 'POST'])
@require_login
@oauth.authorize_handler
def authorize(*args, **kwargs):
    if request.method == 'GET':
        client_id = kwargs.get('client_id')
        client, _ = Client.get_or_create(client_id=client_id)
        kwargs['client'] = client
        return render_template('oauthorize.html', **kwargs)

    confirm = request.form.get('confirm', 'no')
    return confirm == 'yes'


@app.route('/oauth/token')
@oauth.token_handler
def access_token():
    return None

@app.route('/oauth/revoke', methods=['POST'])
@oauth.revoke_handler
def revoke_token():
    pass

@app.route('/api/me')
@oauth.require_oauth()
def me():
    return jsonify(user=current_user)
