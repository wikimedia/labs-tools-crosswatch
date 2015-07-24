#!/bin/bash
venv=$HOME/.virtualenvs/backend/bin
source ${venv}/activate
cd `dirname $0`
${venv}/celery -A backend worker -l info -n crosswatch$1.%n --concurrency=500 -P gevent
