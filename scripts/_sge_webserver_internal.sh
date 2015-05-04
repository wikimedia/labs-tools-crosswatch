#!/bin/bash
source $HOME/.virtualenvs/backend-trusty/bin/activate
source $HOME/crosswatch/scripts/paths.sh
export PORT=$1
echo "running on port $PORT"
cd $BACKEND
python server.py $PORT
