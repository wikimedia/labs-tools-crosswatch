# -*- coding: utf-8 -*-
# ISC License
# Copyright (C) 2015 Jan Lebert
from __future__ import absolute_import
from celery import Celery
from celery.utils.log import get_task_logger
from kombu import Exchange, Queue

from .. import config

logger = get_task_logger(__name__)

BROKER_URL = 'redis://{server}:{port}/{db}'.format(
    server=config.redis_server,
    port=config.redis_port,
    db=config.redis_db
)

app = Celery(broker=BROKER_URL,
             include=['backend.celery.tasks'])

app.conf.update(
    CELERY_TASK_SERIALIZER='json',
    CELERY_ACCEPT_CONTENT=['json'],
    CELERY_IGNORE_RESULT=True,
    CELERY_DISABLE_RATE_LIMITS=True,
    CELERY_DEFAULT_QUEUE=config.toolname,
    CELERY_QUEUES=(
        Queue(config.redis_prefix + 'q', Exchange(config.toolname),
              routing_key=config.toolname),
    ),
    BROKER_TRANSPORT_OPTIONS={
        'fanout_prefix': True,
        'fanout_patterns': True,
        'keyprefix_queue': config.redis_prefix + '.binding.%s',
        'unacked_key': config.redis_prefix + '_unacked',
        'unacked_index_key': config.redis_prefix + '_unacked_index',
        'unacked_mutex_key': config.redis_prefix + '_unacked_mutex'
        },

    CELERY_SEND_TASK_ERROR_EMAILS=True,
    SERVER_EMAIL = config.email,
    ADMINS = [(config.toolname, config.email)],
    EMAIL_HOST = config.mail_server,
    EMAIL_PORT = 25
)
