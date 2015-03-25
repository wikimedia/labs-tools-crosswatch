#!/usr/bin/python
# -*- coding: utf-8 -*-
# MIT License
# Copyright (C) 2014 sitic
"""
   Tornado web server for find-and-replace tool
   running on tools.wmflabs.org/find-and-replace
"""
from __future__ import print_function

from celery import Celery
from simplecrypt import decrypt
import requests
from requests_oauthlib import OAuth1
import json
import redis

import config

from celery.utils.log import get_task_logger
logger = get_task_logger(__name__)

app = Celery()
app.config_from_object('config:celeryconfig')

@app.task
def get_watchlist(obj):
    projects = [
            ['enwiki', 'https://en.wikipedia.org/wiki', 'https://en.wikipedia.org/w/api.php'],
            ['dewiki', 'https://de.wikipedia.org/wiki', 'https://de.wikipedia.org/w/api.php'],
            ['frwiki', 'https://fr.wikipedia.org/wiki', 'https://fr.wikipedia.org/w/api.php'],
            ['itwiki', 'https://it.wikipedia.org/wiki', 'https://it.wikipedia.org/w/api.php'],
            ['commons', 'https://commons.wikimedia.org/wiki', 'https://commons.wikimedia.org/w/api.php'],
            ['wikidata', 'https://www.wikidata.org/wiki/wiki', 'https://www.wikidata.org/w/api.php'],
            ['metawiki', 'https://meta.wikimedia.org/wiki', 'https://meta.wikimedia.org/w/api.php'],
            ['enwiktionary', 'https://en.wiktionary.org/wiki', 'https://en.wiktionary.org/w/api.php'],
            ['dewiktionary', 'https://de.wiktionary.org/wiki', 'https://de.wiktionary.org/w/api.php'],
            ['mediawiki', 'https://www.mediawiki.org/wiki', 'https://www.mediawiki.org/w/api.php']
            ]
    for project in projects:
        watchlistgetter.delay(obj, *project)

@app.task
def watchlistgetter(obj, project, project_url, api_url):
    r = redis.StrictRedis(
            host=config.redis_server,
            port=config.redis_port,
            db=config.redis_db)

    redis_channel = obj['redis_channel']

    access_token = obj['access_token']
    access_token = json.loads(access_token)

    # Construct an auth object with the consumer and access tokens
    auth1 = OAuth1(config.consumer_token.key,
                   client_secret=config.consumer_token.secret,
                   resource_owner_key=access_token['key'],
                   resource_owner_secret=access_token['secret'])

    # Now, accessing the API on behalf of a user
    logger.info("Reading top 70 watchlist items for wiki " + project)
    response = requests.get(
        api_url,
        params={
            'action': "query",
            'list': "watchlist",
            'wlallrev': "",
            'wltype': "edit",
            'wllimit': 70,
            'wlprop': "ids|flags|title|parsedcomment|user|timestamp|sizes|loginfo",
            'format': "json"
        },
        auth=auth1
    )
    href = u'<a href="' + project_url + u'/'
    for item in response.json()['query']['watchlist']:
        item['msgtype'] = 'watchlist'
        item['project'] = project
        item['projecturl'] = project_url
        item['parsedcomment'] = item['parsedcomment'].replace(u'<a href="/wiki/', href)
        r.publish(redis_channel, json.dumps(item))


if __name__ == '__main__':
    app.start()
