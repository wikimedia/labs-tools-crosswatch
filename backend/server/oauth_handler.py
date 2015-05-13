# -*- coding: utf-8 -*-
"""
WSGI container for OAuth login/logout handling.
"""
# ISC License
# Copyright (C) 2015 Jan Lebert
from __future__ import absolute_import
import os

from flask import Flask

from .flask_mwoauth import MWOAuth
from ..config import oauth_consumer_key, oauth_consumer_secret, toolname

app = Flask(__name__)
app.secret_key = os.urandom(24)

mwoauth = MWOAuth(base_url='https://en.wikipedia.org/w',
                  clean_url='https://en.wikipedia.org/wiki',
                  consumer_key=oauth_consumer_key,
                  consumer_secret=oauth_consumer_secret,
                  toolname=toolname)

app.register_blueprint(mwoauth.bp,  url_prefix='/' + toolname)

if __name__ == "__main__":
    app.run()
