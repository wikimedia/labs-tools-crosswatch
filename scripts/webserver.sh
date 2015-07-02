#!/bin/bash
source $HOME/.virtualenvs/backend/bin/activate
cd `dirname $0`
cd ..
python -m backend $PORT
