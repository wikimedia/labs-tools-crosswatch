#!/usr/bin/python
# -*- coding: utf-8 -*-
# MIT License
# Copyright (C) 2014 sitic
"""
   Tornado web server for find-and-replace tool
   running on tools.wmflabs.org/find-and-replace
"""
from __future__ import print_function
import logging

import tornado.ioloop
from tornado.web import StaticFileHandler, FallbackHandler, RedirectHandler
from tornado.web import Application
from tornado.wsgi import WSGIContainer
import sockjs.tornado
import tornadoredis
import tornadoredis.pubsub

import json
import redis
from uuid import uuid4

import config  # general config file
toolname = config.toolname

# import celery

from oauth_handler import app as oauth_wsgi

from tasks import get_watchlist

# Use the synchronous redis client to publish messages to a channel
redis_client = redis.StrictRedis(host=config.redis_server,
                                 port=config.redis_port,
                                 db=config.redis_db)
# Create the tornadoredis.Client instance
# and use it for redis channel subscriptions
subscriber = tornadoredis.pubsub.SockJSSubscriber(tornadoredis.Client(
    host=config.redis_server,
    port=config.redis_port,
    selected_db=config.redis_db))


class SockConnection(sockjs.tornado.SockJSConnection):
    def on_open(self, info):
        self.channels = []

    def on_close(self):
        for channel in self.channels:
            subscriber.unsubscribe(channel, self)

    def on_message(self, message):
        data = json.loads(message)
        print(data)
        if data[u'action'] == u'watchlist':
            redis_channel = str(uuid4())
            self.channels.append(redis_channel)
            logging.info('New redis channel ' + redis_channel)
            subscriber.subscribe(redis_channel, self)
            data['redis_channel'] = redis_channel
            get_watchlist.delay(data)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',  # NOQA
                        datefmt='%m-%d %H:%M')

    import sys
    if len(sys.argv) < 2:
        print("ERROR: no first argument given. Quitting", file=sys.stderr)
        sys.exit(1)
    PORT = int(sys.argv[1])

    # Config sockjs
    SockRouter = sockjs.tornado.SockJSRouter(SockConnection,
                                             '/' + toolname + '/sockjs')

    OauthApp = WSGIContainer(oauth_wsgi)
    # Config oauth consumer
    OauthRouter = [(r"/" + toolname + r"/login",
                    FallbackHandler, dict(fallback=OauthApp)),
                   (r"/" + toolname + r"/logout",
                    FallbackHandler, dict(fallback=OauthApp)),
                   (r"/" + toolname + r"/oauth-callback",
                    FallbackHandler, dict(fallback=OauthApp))]

    # Config routes
    import os
    pwd_path = os.path.dirname(__file__)

    static_path = os.path.join(pwd_path, 'public')
    index_path = os.path.join(pwd_path, 'public/' + toolname + '/index.html')
    static_handlers = [
        (r"/()",     StaticFileHandler, {"path": index_path}),
        (r"/" + toolname + r"/()", StaticFileHandler, {"path": index_path}),
        (r"/" + toolname, RedirectHandler, {"url": "/" + toolname + "/"}),
        (r"/(.*)",   StaticFileHandler, {"path": static_path})
        ]

    routes = OauthRouter + SockRouter.urls + static_handlers
    app = Application(routes)

    # Start the server
    app.listen(PORT)
    tornado.ioloop.IOLoop.instance().start()
