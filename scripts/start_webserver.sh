#!/bin/bash
cd `dirname $0`
echo "starting webserver"
jstart -N tornado-crosswatch -once -q webgrid-generic -l release=trusty -mem 3G ./_sge_webserver.sh
