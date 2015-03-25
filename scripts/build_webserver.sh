#!/bin/bash
source $HOME/.virtualenvs/build/bin/activate
source ./paths.sh
cd $FRONTEND
gulp build
