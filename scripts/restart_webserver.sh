#!/bin/bash
cd `dirname $0`
./stop_webserver.sh
while [ "$(qstat -q webgrid-generic | wc -l)" -ge 3 ]; do
    sleep 1
done
./start_webserver.sh
