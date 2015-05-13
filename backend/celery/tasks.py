# -*- coding: utf-8 -*-
"""Celery tasks"""
# ISC License
# Copyright (C) 2015 Jan Lebert
from __future__ import absolute_import

from . import app, logger
from .api import MediaWiki


@app.task
def initial_task(obj):
    mw = MediaWiki(access_token=obj['access_token'])
    wikis = mw.get_wikis()
    projects = ['enwiki', 'dewiki', 'itwiki', 'frwiki', 'itwiki',
                'commonswiki', 'wikidatawiki', 'enwiktionary', 'dewiktionary',
                'metawiki', 'mediawikiwiki']
    for project in projects:
        obj['wiki'] = wikis[project]
        watchlistgetter.delay(obj)


def fix_urls(html, url):
    a = u'<a target="_blank" href="' + url + u'/'
    html = html.replace(u'<a href="/', a)
    return html


@app.task
def watchlistgetter(obj):
    """
    Get the watchlist for a wiki
    :param obj: dict with wiki and connection information
    """
    logger.info("Reading watchlist items for wiki " +
                obj['wiki']['dbname'])
    mw = MediaWiki(host=obj['wiki']['url'],
                   access_token=obj['access_token'],
                   redis_channel=obj['redis_channel'])
    if 'watchlistperiod' in obj:
        days = obj['watchlistperiod']
    else:
        days = 1
    params = {
        'list': "watchlist",
        'wlallrev': "",
        'wltype': "edit|new",
        'wllimit': 500,
        'wlend': mw.timestamp(daysdelta=-days),
        'wlprop': "ids|flags|title|parsedcomment|user|timestamp|sizes|" +
        "notificationtimestamp|loginfo"
    }

    for response in mw.query_gen(params):
        items = []
        for item in response['watchlist']:
            item['project'] = obj['wiki']['dbname']
            item['projecturl'] = obj['wiki']['url']

            if 'commenthidden' in item:
                item['parsedcomment'] = "<s>edit summary removed</s>"
            item['parsedcomment'] = fix_urls(item['parsedcomment'],
                                             obj['wiki']['url'])
            item['projectgroup'] = obj['wiki']['group']
            item['projectlang'] = obj['wiki']['lang']
            item['projectlangname'] = obj['wiki']['langname']
            if 'bot' in item:
                item['bot'] = "b"
            if 'minor' in item:
                item['minor'] = "m"
            if 'new' in item:
                item['new'] = "n"
            items.append(item)
        message = {
            'msgtype': 'watchlist',
            'entires': items
        }
        if items:
            mw.publish(message)


if __name__ == '__main__':
    app.start()
