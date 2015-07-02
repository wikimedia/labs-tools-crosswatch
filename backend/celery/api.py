# -*- coding: utf-8 -*-
# ISC License
# Copyright (C) 2015 Jan Lebert
from __future__ import absolute_import
import requests
from requests_oauthlib import OAuth1
from redis import StrictRedis
import json
from datetime import datetime, timedelta

from .. import config
from . import logger


class MediaWiki(object):
    def __init__(self, host="https://en.wikipedia.org", path="/w/api.php",
                 access_token=None, redis_channel=None):
        self.api_url = host + path
        self.wikis = {}

        user_agent = "crosswatch (https://tools.wmflabs.org/crosswatch;" +\
            "crosswatch@tools.wmflabs.org) python-requests/" +\
            requests.__version__
        self.headers = {'User-Agent': user_agent}

        if access_token:
            # Construct an auth object with the consumer and access tokens
            access_token = json.loads(access_token)
            self.auth = OAuth1(config.consumer_token.key,
                               client_secret=config.consumer_token.secret,
                               resource_owner_key=access_token['key'],
                               resource_owner_secret=access_token['secret'])
        else:
            self.auth = None

        self.redis_channel = redis_channel
        self.redis = StrictRedis(
            host=config.redis_server,
            port=config.redis_port,
            db=config.redis_db
        )

    def publish(self, message):
        if not self.redis_channel:
            raise Exception("No redis channel set to publish to")
        self.redis.publish(self.redis_channel, json.dumps(message))

    @staticmethod
    def timestamp(daysdelta=0):
        """
        :param daysdelta: calculate timestamp in ´daysdelta´ days
        :return: MediaWIki timestamp format
        """
        now = datetime.utcnow()
        delta = timedelta(days=daysdelta)
        time = now + delta
        return time.strftime("%Y%m%d%H%M%S")

    @staticmethod
    def handle_response(response):
        if 'error' in response:
            logger.error(response['error'])
            if response['error']['code'] == "mwoauth-invalid-authorization":
                raise Exception("OAuth authentication failed")

            raise Exception(str(response['error']))
        if 'warnings' in response:
            logger.warn("API-request warning: " + str(response['warnings']))

    def query(self, params):
        params['format'] = "json"
        response = requests.get(self.api_url, params=params, auth=self.auth,
                                headers=self.headers).json()

        self.handle_response(response)
        return response

    def query_gen(self, params):
        params['format'] = "json"
        params['action'] = "query"
        last_continue = {'continue': ""}
        while True:
            p = params.copy()
            p.update(last_continue)
            response = requests.get(self.api_url, params=p, auth=self.auth,
                                    headers=self.headers).json()

            if 'error' in response:
                raise Exception(str(response['error']))
            if 'warnings' in response:
                warning = response['warnings']['query']['*']
                logger.warn("API-request warning: " + warning)
            if 'query' in response:
                yield response['query']
            if 'continue' not in response:
                break
            last_continue = response['continue']

    def post(self, params, payload, token_type='csrf'):
        params['format'] = "json"

        token = self.get_token(token_type)
        payload['token'] = token

        response = requests.post(self.api_url, params=params, data=payload,
                                 auth=self.auth, headers=self.headers)

        self.handle_response(json.loads(response.text))

    def get_token(self, type='csrf'):
        params = {'action': "query",
                  'meta': "tokens",
                  'type': type}
        r = self.query(params)
        token = r['query']['tokens'][type + 'token']
        return token

    def get_username(self):
        try:
            params = {
                'action': "query",
                'meta': "userinfo",
            }
            response = self.query(params)
            username = response['query']['userinfo']['name']
            return username
        except KeyError as e:
            if response['error']['code'] == "mwoauth-invalid-authorization":
                logger.error('mwoauth-invalid-authorization')
                raise Exception("OAuth authentication failed")
            raise e

    def get_wikis(self, use_cache=True):
        key = config.redis_prefix + 'cached_wikis'
        wikis = self.redis.get(key)
        if use_cache and wikis:
            wikis = json.loads(wikis)
        else:
            # Cache miss, do api request and fill cache
            wikis = self._get_wikis()
            self.redis.setex(key, 86400, json.dumps(wikis))  # 1 day exp.

        return wikis

    def _get_wikis(self):
        params = {'action': "sitematrix"}
        data = self.query(params)
        for key, val in data['sitematrix'].items():
            if key == 'count':
                continue

            if 'code' in val:
                for site in val['site']:
                    self._parse_sitematrix(site, val['code'], val['name'])
            else:
                for site in val:
                    self._parse_sitematrix(site, '', '')

        return self.wikis

    def _parse_sitematrix(self, site, lang, langname):
        wiki = {
            'lang': lang,
            'langname': langname,
            'url': site['url'].replace("http://", "https://"),
            'dbname': site['dbname'],
            'group': site['code']
        }
        if wiki['group'] == 'wiki':
            wiki['group'] = 'wikipedia'

        inactive_wikis = ['closed', 'private', 'fishbowl']
        if any([key in site for key in inactive_wikis]):
            wiki['closed'] = True

        self.wikis[site['dbname']] = wiki
