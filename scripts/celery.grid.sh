#!/bin/bash
#jsub -once -continuous -l h_vmem=512M -N rahu -M jan.lebert@online.de -m abe /data/project/asurabot/scripts/rahu.grid.sh
source $HOME/.virtualenvs/backend/bin/activate
source $HOME/crosswatch/scripts/paths.sh
cd $BACKEND
celery -A tasks worker -l info
# --autoreload
