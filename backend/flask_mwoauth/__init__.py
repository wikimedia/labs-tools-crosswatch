#!/usr/bin/env python
# MediaWiki OAuth connector for Flask
#
# Requires flask-oauth
#
# (C) 2013 Merlijn van Deen <valhallasw@arctus.nl>
# (C) 2015 Sitic
# Licensed under the MIT License // http://opensource.org/licenses/MIT
#

__version__ = '0.1.35'

import sys
import urllib
from flask import request, session, Blueprint, make_response
from flask_oauth import OAuth, OAuthRemoteApp, OAuthException, parse_response
import json


class MWOAuthRemoteApp(OAuthRemoteApp):
    def handle_oauth1_response(self):
        """Handles an oauth1 authorization response.  The return value of
        this method is forwarded as first argument to the handling view
        function.
        """
        client = self.make_client()
        resp, content = client.request('%s&oauth_verifier=%s' % (
            self.expand_url(self.access_token_url),
            request.args['oauth_verifier'],
        ), self.access_token_method)
        print resp, content
        data = parse_response(resp, content)
        if not self.status_okay(resp):
            raise OAuthException('Invalid response from ' + self.name,
                                 type='invalid_response', data=data)
        return data


class MWOAuth(object):  # http://stackoverflow.com/a/26691512
    def __init__(self,
                 base_url='https://www.mediawiki.org/w',
                 clean_url='https://www.mediawiki.org/wiki',
                 consumer_key=None,
                 consumer_secret=None,
                 toolname='crosswatch'):
        if not consumer_key or not consumer_secret:
            raise Exception('MWOAuthBlueprintFactory needs consumer key and\
                            secret')
        self.base_url = base_url
        self.toolname = toolname

        self.oauth = OAuth()
        self.mwoauth = MWOAuthRemoteApp(self.oauth, 'mw.org',
            base_url = base_url + "/index.php",
            request_token_url=base_url + "/index.php",
            request_token_params = {'title': 'Special:OAuth/initiate',
                                    'oauth_callback': 'oob'},
            access_token_url=base_url + "/index.php?title=Special:OAuth/token",
            authorize_url=clean_url + '/Special:OAuth/authorize',
            consumer_key=consumer_key,
            consumer_secret=consumer_secret,
        )
        self.oauth.remote_apps['mw.org'] = self.mwoauth

        @self.mwoauth.tokengetter
        def get_mwo_token(token=None):
            return session.get('mwo_token')

        self.bp = Blueprint('mwoauth', __name__)

        @self.bp.route('/login')
        def login():
            redirector = self.mwoauth.authorize()

            if 'next' in request.args:
                oauth_token = session[self.mwoauth.name + '_oauthtok'][0]
                session[oauth_token + '_target'] = request.args['next']

            redirector.headers['Location'] += "&oauth_consumer_key=" +\
                self.mwoauth.consumer_key
            return redirector

        @self.bp.route('/oauth-callback')
        @self.mwoauth.authorized_handler
        def oauth_authorized(resp):
            if resp is None:
                return 'You denied the request to sign in.'
            session['mwo_token'] = (
                resp['oauth_token'],
                resp['oauth_token_secret']
            )

            username = self.get_current_user(False)

            mwo_token = {'key': resp['oauth_token'],
                         'secret': resp['oauth_token_secret']}
            mwo_token = json.dumps(mwo_token)

            resp = make_response('This tab should close automatically.' +
                                 '<script>self.close()</script>')
            resp.set_cookie(self.toolname + 'Auth', mwo_token,
                            max_age=30*24*60*60,
                            path='/' + self.toolname + '/')
            resp.set_cookie(self.toolname + 'User', username,
                            max_age=30*24*60*60,
                            path='/' + self.toolname + '/')
            session.clear()

            return resp

        @self.bp.route('/logout')
        def logout():
            resp = make_response('You are now logged out. Goodbye :-)')
            session['mwo_token'] = None
            resp.set_cookie(self.toolname + 'Auth', '',
                            path='/' + self.toolname + '/', expires=0)
            resp.set_cookie(self.toolname + 'User', '',
                            path='/' + self.toolname + '/', expires=0)
            session.clear()

            return resp

    def request(self, api_query, url=None):
        """ e.g. {'action': 'query', 'meta': 'userinfo'}.
            format=json not required. Function returns a python dict
            that resembles the api's json response
        """
        api_query['format'] = 'json'
        url = url or self.base_url

        size = sum([sys.getsizeof(v) for k, v in api_query.iteritems()])

        if size > (1024 * 8):
            # if request is bigger than 8 kB (the limit is somewhat arbitrary,
            # see https://www.mediawiki.org/wiki/API:Edit#Large_texts) then
            # transmit as multipart message

            req = self._prepare_long_request(url=url + "/api.php?",
                                             api_query=api_query
                                             )
            return self.mwoauth.post(url + "/api.php?",
                                     data=req.body,
                                     content_type=req.headers['Content-Type']
                                     ).data
        else:
            return self.mwoauth.post(url + "/api.php?" +
                                     urllib.urlencode(api_query),
                                     content_type="text/plain").data

    def get_current_user(self, cached=True):
        if cached:
            return session.get('username')

        try:
            data = self.request({'action': 'query', 'meta': 'userinfo'})
            session['username'] = data['query']['userinfo']['name']
        except KeyError:
            session['username'] = None
        except OAuthException:
            session['username'] = None
        return session['username']
