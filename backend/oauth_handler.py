import os
from flask import Flask
from flask_mwoauth import MWOAuth
import config

app = Flask(__name__)

# Generate a random secret application key
#
# NOTE: this key changes every invocation. In an actual application, the key
# should not change! Otherwise you might get a different secret key for
# different requests, which means you can't read data stored in cookies,
# which in turn breaks OAuth.
#
# So, for an actual application, use app.secret_key = "some long secret key"
# (which you could generate using os.urandom(24))
#
app.secret_key = os.urandom(24)

consumer_key = config.oauth_consumer_key
consumer_secret = config.oauth_consumer_secret
toolname = config.toolname

mwoauth = MWOAuth(consumer_key=consumer_key,
                  consumer_secret=consumer_secret)

app.register_blueprint(mwoauth.bp,  url_prefix='/' + toolname)

if __name__ == "__main__":
    app.run()
