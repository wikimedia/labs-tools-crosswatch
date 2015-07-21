# -*- coding: utf-8 -*-
"""
Tornado web server for crosswatch tool
running on https://tools.wmflabs.org/crosswatch

"""
#
# ISC License
# Copyright (C) 2014 Jan Lebert
from __future__ import absolute_import
from __future__ import unicode_literals
import os

import logging
import json
from uuid import uuid4

import tornado.ioloop
from tornado.web import StaticFileHandler, FallbackHandler, RedirectHandler,\
    Application
from tornado.wsgi import WSGIContainer
from sockjs.tornado import SockJSConnection, SockJSRouter
from tornadoredis import Client as RedisClient
from tornadoredis.pubsub import SockJSSubscriber

from .. import config
toolname = config.toolname
from .oauth_handler import app as oauth_wsgi
from ..celery import app as celery_app

# Create the tornadoredis.Client instance
# and use it for redis channel subscriptions
subscriber = SockJSSubscriber(RedisClient(
    host=config.redis_server,
    port=config.redis_port,
    selected_db=config.redis_db
    ))


class SockConnection(SockJSConnection):
    def on_open(self, info):
        self.channels = []

    def on_close(self):
        for channel in self.channels:
            subscriber.unsubscribe(channel, self)

    def on_message(self, message):
        data = json.loads(message)
        if data['action'] == 'watchlist':
            redis_channel = str(uuid4())
            self.channels.append(redis_channel)

            logging.info('New redis channel ' + redis_channel)
            subscriber.subscribe(redis_channel, self)

            data['redis_channel'] = redis_channel
            celery_app.send_task('backend.celery.tasks.initial_task',
                                 kwargs=data, expires=60)
        elif data['action'] == 'notifications_mark_read':
            celery_app.send_task('backend.celery.tasks.notifications_mark_read',
                                 kwargs=data, expires=60)
        elif data['action'] == 'diff':
            redis_channel = str(uuid4())
            self.channels.append(redis_channel)
            subscriber.subscribe(redis_channel, self)

            data['redis_channel'] = redis_channel
            celery_app.send_task('backend.celery.tasks.get_diff', kwargs=data)


class NoChacheStaticFileHandler(StaticFileHandler):
    def set_extra_headers(self, path):
        self.set_header('Cache-Control', 'no-store, no-cache, ' +
                        'must-revalidate, max-age=0')


def run(port):
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s %(name)-12s %(levelname)-8s' +
                               ' %(message)s',
                        datefmt='%m-%d %H:%M')
    logging.info("Starting tornado server on port %d." % port)

    # Config sockjs
    sockjs_settings = {
        "sockjs_url": "https://tools-static.wmflabs.org/cdnjs/ajax/libs/sockjs-client/1.0.0/sockjs.min.js"
    }
    sockjsrouter = SockJSRouter(SockConnection, '/' + toolname + '/sockjs',
                                user_settings=sockjs_settings)

    oauthapp = WSGIContainer(oauth_wsgi)
    # Config oauth consumer
    oauthrouter = [(r"/" + toolname + r"/login",
                    FallbackHandler, dict(fallback=oauthapp)),
                   (r"/" + toolname + r"/logout",
                    FallbackHandler, dict(fallback=oauthapp)),
                   (r"/" + toolname + r"/oauth-callback",
                    FallbackHandler, dict(fallback=oauthapp))]

    # Config routes
    pwd_path = os.path.dirname(__file__)

    static_path = os.path.join(pwd_path, 'public')
    index_path = os.path.join(pwd_path, 'public/' + toolname + '/index.html')
    static_handlers = [
        (r"/()", NoChacheStaticFileHandler, {"path": index_path}),
        (r"/" + toolname + r"/\w*()", NoChacheStaticFileHandler,
         {"path": index_path}),
        (r"/" + toolname, RedirectHandler, {"url": "/" + toolname + "/"}),
        (r"/(.*)", StaticFileHandler, {"path": static_path})
        ]

    routes = oauthrouter + sockjsrouter.urls + static_handlers
    app = Application(routes)

    # Start the server
    app.listen(port)
    tornado.ioloop.IOLoop.instance().start()
