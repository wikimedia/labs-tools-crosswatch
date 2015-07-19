# -*- coding: utf-8 -*-
"""Celery tasks"""
# ISC License
# Copyright (C) 2015 Jan Lebert
from __future__ import absolute_import

from uuid import uuid4
from contextlib import closing
import MySQLdb

from .. import config
from . import app, logger
from .api import MediaWiki


def chunks(l, n):
    """
    Yield successive n-sized chunks from l.

    """
    for i in xrange(0, len(l), n):
        yield l[i:i+n]


@app.task
def initial_task(obj):
    """
    Task called on login, start the chain to load the
    watchlist, notifications etc.
    :param obj: dict with redis channel and oauth keys

    """
    mw = MediaWiki(access_token=obj['access_token'])
    username = mw.username()
    wikis = mw.wikis()

    # Use cache of known projects to bypass sometimes blocking mysql check
    preload_projects = obj.pop('projects', [])
    for project in preload_projects:
        obj['wiki'] = wikis[project]
        watchlistgetter.delay(obj)
        notificationgetter.delay(obj)

    db = MySQLdb.connect(
        host='centralauth.labsdb',
        user=config.sql_user,
        passwd=config.sql_passwd
    )

    projects = []
    with closing(db.cursor()) as cur:
        cur.execute("SELECT lu_wiki FROM centralauth_p.localuser WHERE lu_name=%s;", [username])  # NOQA
        result = cur.fetchall()
        for row in result:
            project = row[0]
            try:
                wiki = wikis[project]
                if 'closed' not in wiki and project not in preload_projects:
                    projects.append(wiki)
            except KeyError:
                logger.error("Could not find %s in list of wikis" % project)
    db.close()

    for chunk in chunks(projects, 50):
        check_editcount.delay(obj, chunk, username)


@app.task
def check_editcount(obj, project_chunk, username):
    """
    Starts the watchlist- and notificationgetter if the
    user has made more than one edit to a project
    :param obj: The dict from tornado
    :param project_chunk: list of projets
    :param username:

    """
    db = MySQLdb.connect(
        host='s4.labsdb',
        user=config.sql_user,
        passwd=config.sql_passwd
    )
    with closing(db.cursor()) as cur:
        for wiki in project_chunk:
            project = wiki['dbname']
            cur.execute("SELECT user_editcount FROM `%s_p`.user  WHERE user_name='%s';" % (project, username))  # NOQA
            result = cur.fetchone()

            if result and int(result[0]) >= 1:
                obj['wiki'] = wiki
                watchlistgetter.delay(obj)
                notificationgetter.delay(obj)

    db.close()


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
    mw = MediaWiki(host=obj['wiki']['url'],
                   access_token=obj['access_token'],
                   redis_channel=obj['redis_channel'])
    if 'watchlistperiod' in obj:
        days = float(obj['watchlistperiod'])
    else:
        days = 2
    params = {
        'list': "watchlist",
        'wltype': "edit|new|log",
        'wllimit': 500,
        'wlend': mw.timestamp(daysdelta=-days),
        'wlprop': "ids|flags|title|parsedcomment|userid|user|timestamp|" +
        "sizes|notificationtimestamp|loginfo"
    }

    if 'allrev' in obj and obj['allrev']:
        params['wlallrev'] = ""

    for response in mw.query_gen(params):
        items = []
        for item in response['watchlist']:
            item['project'] = obj['wiki']['dbname']
            item['projecturl'] = obj['wiki']['url']
            item['projectgroup'] = obj['wiki']['group']
            item['projectlang'] = obj['wiki']['lang']
            item['projectlangname'] = obj['wiki']['langname']

            if 'commenthidden' in item:
                item['parsedcomment'] = "<s>edit summary removed</s>"
            item['parsedcomment'] = fix_urls(item['parsedcomment'],
                                             obj['wiki']['url'])
            if 'bot' in item:
                item['bot'] = "b"
            if 'minor' in item:
                item['minor'] = "m"
            if 'new' in item:
                item['new'] = "n"

            # random id
            item['id'] = uuid4().hex[:8]
            items.append(item)
        message = {
            'msgtype': 'watchlist',
            'entires': items
        }
        if items:
            mw.publish(message)


@app.task
def notificationgetter(obj):
    """
    Get the echo notifications for a wiki
    :param obj: dict with wiki and connection information
    """
    mw = MediaWiki(host=obj['wiki']['url'],
                   access_token=obj['access_token'],
                   redis_channel=obj['redis_channel'])
    params = {
        'action': "query",
        'meta': "notifications",
        'notprop': "list",
        'notformat': "html",
        'notalertunreadfirst': "",
        'notmessagecontinue': "",
        'notlimit': 15
        }
    response = mw.query(params)

    result = response['query']['notifications']['list']
    if not result:
        return

    event = {
        'msgtype': 'notification',
        'project': obj['wiki']['dbname'],
        'projecturl': obj['wiki']['url'],
        'projectgroup': obj['wiki']['group'],
        'projectlang': obj['wiki']['lang'],
        'projectlangname': obj['wiki']['langname']
    }
    for item in result.values():
        if 'read' in item:
            continue

        event['id'] = item['id']
        # random id
        event['uuid'] = uuid4().hex[:8]

        event['comment'] = fix_urls(item['*'], obj['wiki']['url'])
        event['timestamp'] = item['timestamp']['utcunix']

        mw.publish(event)


@app.task
def notifications_mark_read(obj):
    """
    Mark echo notifications as read
    """
    mw = MediaWiki(access_token=obj['access_token'])
    wikis = mw.wikis()
    params = {'action': "echomarkread"}

    for project, notifications in obj['notifications'].iteritems():
        projecturl = wikis[project]['url']
        mw = MediaWiki(host=projecturl, access_token=obj['access_token'])

        payload = {'list': notifications}
        mw.post(params, payload)


@app.task
def get_diff(obj):
    """
    Get a diff for a wiki page
    """
    mw = MediaWiki(host=obj['projecturl'],
                   access_token=obj['access_token'],
                   redis_channel=obj['redis_channel'])

    diff = mw.diff(obj['pageid'], obj['old_revid'], obj['revid'])
    mw.publish({
        'msgtype': 'diff_response',
        'request_id': obj['request_id'],
        'diff': diff
    })


if __name__ == '__main__':
    app.start()
