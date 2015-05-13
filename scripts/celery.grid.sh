#!/bin/bash
source $HOME/.virtualenvs/backend/bin/activate
cd `dirname $0`
cd ..
celery -A backend worker -l info -n crosswatch$1.%n
