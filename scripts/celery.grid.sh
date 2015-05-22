#!/bin/bash
source $HOME/.virtualenvs/backend/bin/activate
cd `dirname $0`
#celery -A backend worker -l info -n crosswatch$1.%n
celery -A backend worker -l info -n crosswatch$1.%n --concurrency=1000 -P eventlet
