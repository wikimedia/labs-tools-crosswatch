# -*- coding: utf-8 -*-
"""Celery tasks"""
# ISC License
# Copyright (C) 2015 Jan Lebert
from __future__ import absolute_import
from __future__ import unicode_literals
from builtins import range

from uuid import uuid4
from contextlib import closing
import MySQLdb

from .. import config
from . import app, logger
from .api import MediaWiki


def chunks(l, n):
    """Yield successive n-sized chunks from l."""
    for i in range(0, len(l), n):
        yield l[i:i+n]


@app.task
def canary(redis_channel=None, **kwargs):
    """A canary in a coal mine"""
    mw = MediaWiki(redis_channel=redis_channel)
    mw.publish({'msgtype': "canary"})


@app.task
def initial_task(**kwargs):
    """
    Task called on login, start the chain to load the
    watchlist, notifications etc.
    """
    access_token = kwargs['access_token']
    preload_projects = kwargs.get('projects', [])
    redis_channel = kwargs.get('redis_channel', None)

    mw = MediaWiki(access_token=access_token, redis_channel=redis_channel)
    username = mw.user_info().name
    wikis = mw.wikis()

    # Use cache of known projects to bypass sometimes blocking mysql check
    for project in preload_projects:
        wiki = wikis[project]
        watchlistgetter.delay(wiki=wiki, username=username, **kwargs)
        notificationgetter.delay(wiki=wiki, **kwargs)

    db = MySQLdb.connect(
        host='centralauth.labsdb',
        user=config.sql_user,
        passwd=config.sql_passwd,
        charset='utf8'
    )

    projects = []
    with closing(db.cursor()) as cur:
        cur.execute("SELECT lu_wiki FROM centralauth_p.localuser WHERE lu_name=%s;", [username])  # NOQA
        result = cur.fetchall()
        for row in result:
            project = row[0].decode("utf-8")
            try:
                wiki = wikis[project]
                if 'closed' not in wiki and project not in preload_projects:
                    projects.append(wiki)
            except KeyError:
                logger.error("Could not find %s in list of wikis" % project)
    db.close()

    for chunk in chunks(projects, 50):
        check_editcount.delay(chunk, username, **kwargs)

    # Send back canary reply to show that the server is working
    canary(redis_channel=redis_channel)


@app.task
def check_editcount(project_chunk, username, **kwargs):
    """
    Starts the watchlist- and notificationgetter if the
    user has made more than one edit to a project
    :param project_chunk: list of projets
    :param username: username
    """
    db = MySQLdb.connect(
        host='s4.labsdb',
        user=config.sql_user,
        passwd=config.sql_passwd,
        charset='utf8'
    )
    with closing(db.cursor()) as cur:
        for wiki in project_chunk:
            project = wiki['dbname']
            cur.execute("SELECT user_editcount FROM `%s_p`.user  WHERE user_name='%s';" % (project, username))  # NOQA
            result = cur.fetchone()

            if result and int(result[0]) >= 1:
                watchlistgetter.delay(wiki=wiki, username=username, **kwargs)
                notificationgetter.delay(wiki=wiki, **kwargs)

    db.close()


def fix_urls(html, url):
    a = '<a target="_blank" href="' + url + '/'
    html = html.replace('<a href="/', a)
    return html


@app.task
def watchlistgetter(**kwargs):
    """Get the watchlist for a wiki"""
    wiki = kwargs['wiki']
    access_token = kwargs['access_token']
    redis_channel = kwargs['redis_channel']
    watchlistperiod = kwargs.get('watchlistperiod', False)
    allrev = kwargs.get('allrev', False)

    mw = MediaWiki(host=wiki['url'], access_token=access_token,
                   redis_channel=redis_channel)

    if watchlistperiod:
        days = float(watchlistperiod)
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

    if allrev:
        params['wlallrev'] = ""

    for response in mw.query_gen(params):
        items = []
        for item in response['watchlist']:
            item['project'] = wiki['dbname']
            item['projecturl'] = wiki['url']
            item['projectgroup'] = wiki['group']
            item['projectlang'] = wiki['lang']
            item['projectlangname'] = wiki['langname']

            if 'commenthidden' in item:
                item['parsedcomment'] = "<s>edit summary removed</s>"
            item['parsedcomment'] = fix_urls(item['parsedcomment'],
                                             wiki['url'])
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
        if not items:
            return
        mw.publish(message)

        if wiki.get('flaggedrevs', False):
            flagged_revs.delay(params, items, **kwargs)

        if mw.ores_context_exists(wiki['dbname']):
            ores.delay(items, **kwargs)


@app.task
def notificationgetter(**kwargs):
    """Get the echo notifications for a wiki"""
    wiki = kwargs['wiki']
    access_token = kwargs['access_token']
    redis_channel = kwargs['redis_channel']

    mw = MediaWiki(host=wiki['url'], access_token=access_token,
                   redis_channel=redis_channel)

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
        'project': wiki['dbname'],
        'projecturl': wiki['url'],
        'projectgroup': wiki['group'],
        'projectlang': wiki['lang'],
        'projectlangname': wiki['langname']
    }
    for item in result.values():
        if 'read' in item:
            continue

        event['id'] = item['id']
        # random id
        event['uuid'] = uuid4().hex[:8]

        event['comment'] = fix_urls(item['*'], wiki['url'])
        event['timestamp'] = item['timestamp']['utcunix']

        mw.publish(event)


@app.task
def notifications_mark_read(**kwargs):
    """Mark echo notifications as read"""
    access_token = kwargs['access_token']
    redis_channel = kwargs['redis_channel']
    notifications = kwargs.get('notifications', {})

    mw = MediaWiki(access_token=access_token, redis_channel=redis_channel)
    wikis = mw.wikis()

    for project, notifications in notifications.items():
        projecturl = wikis[project]['url']
        mw = MediaWiki(host=projecturl, access_token=access_token,
                       redis_channel=redis_channel)

        params = {'action': "echomarkread"}
        payload = {'list': notifications}
        mw.post(params, payload)


@app.task
def get_diff(access_token=None, redis_channel=None, **kwargs):
    """Get a diff for a wiki page"""
    projecturl = kwargs['projecturl']
    pageid = kwargs['pageid']
    old_revid = kwargs['old_revid']
    revid = kwargs['revid']
    request_id = kwargs['request_id']

    mw = MediaWiki(host=projecturl,
                   access_token=access_token,
                   redis_channel=redis_channel)

    diff = mw.diff(pageid, old_revid, revid)
    mw.publish({
        'msgtype': 'response',
        'request_id': request_id,
        'data': diff
    })


@app.task
def watch(**kwargs):
    access_token = kwargs['access_token']
    redis_channel = kwargs['redis_channel']
    request_id = kwargs['request_id']
    projecturl = kwargs['projecturl']
    title = kwargs['title']
    watchted = kwargs['status']

    mw = MediaWiki(host=projecturl,
                   access_token=access_token,
                   redis_channel=redis_channel)

    params = {'action': "watch"}
    payload = {'titles': title}
    if watchted:
        payload['unwatch'] = ""
    mw.post(params, payload, token_type='watch')

    mw.publish({
        'msgtype': 'response',
        'request_id': request_id,
        'data': not watchted
    })


@app.task
def ores(items, **kwargs):
    wiki = kwargs['wiki']
    access_token = kwargs['access_token']
    redis_channel = kwargs['redis_channel']

    mw = MediaWiki(host=wiki['url'],
                   access_token=access_token,
                   redis_channel=redis_channel)

    edits = {}
    for item in items:
        if item['type'] == 'edit':
            edits[item['revid']] = item
    if not edits:
        return

    response = mw.ores_scores(wiki['dbname'], edits.keys())
    for revid, value in response.items():
        if 'error' in value:
            logger.warning('ORES error {} for revid {}, response: {}'.format(
                value['error']['message'], revid, value))
            continue
        if value['probability']['true'] >= 0.8:
            revid = int(revid)
            probablity = "{:.0%}".format(value['probability']['true'])
            _ores_diff.delay(edits[revid], probablity, **kwargs)


@app.task
def _ores_diff(edit, probablity, **kwargs):
    wiki = kwargs['wiki']
    access_token = kwargs['access_token']
    redis_channel = kwargs['redis_channel']

    mw = MediaWiki(host=wiki['url'],
                   access_token=access_token,
                   redis_channel=redis_channel)

    if mw.was_reverted(edit):
        return

    diff = mw.diff(edit['pageid'], edit['old_revid'], edit['revid'])
    mw.publish({
        'msgtype': "ores_scores",
        'id': edit['id'],
        'diff': diff,
        'oresProbability': probablity
    })


@app.task
def flagged_revs(watchlist_params, items, **kwargs):
    wiki = kwargs['wiki']
    access_token = kwargs['access_token']
    redis_channel = kwargs['redis_channel']
    username = kwargs['username']

    mw = MediaWiki(host=wiki['url'],
                   access_token=access_token,
                   redis_channel=redis_channel)

    if 'review' not in mw.user_rights(username):
        return

    params = {
        'prop': "flagged",
        'generator': "watchlist"
    }
    for key in watchlist_params:
        if key.startswith('wl'):
            params['g' + key] = watchlist_params[key]

    unstable = {}
    for response in mw.query_gen(params):
        for pageid, item in response['pages'].items():
            flagged = item.get('flagged', {})
            if 'pending_since' in flagged:
                unstable[int(pageid)] = flagged['stable_revid']
    if not unstable:
        return

    for pageid, stable_revid in unstable.items():
        for item in items:
            if item['type'] == 'edit' and pageid == item['pageid'] and \
                            stable_revid < item['revid']:
                diff = mw.diff(pageid, item['old_revid'], item['revid'])
                mw.publish({
                    'msgtype': "flaggedrevs",
                    'id': item['id'],
                    'diff': diff,
                    'stableRevid': stable_revid
                })


if __name__ == '__main__':
    app.start()
