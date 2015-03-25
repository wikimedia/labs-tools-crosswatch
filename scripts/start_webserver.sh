#!/bin/bash
cd `dirname $0`
echo "starting webserver"
jstart -N tornado -q webgrid-generic -l release=trusty -mem 4096M ./_sge_webserver.sh
