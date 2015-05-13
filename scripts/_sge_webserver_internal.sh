#!/bin/bash
source $HOME/.virtualenvs/backend/bin/activate
cd `dirname $0`
cd ..
export PORT=$1
python -m backend $PORT
