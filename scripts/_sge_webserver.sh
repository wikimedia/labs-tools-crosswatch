#!/bin/bash
cd `dirname $0`
exec portgrabber crosswatch ./_sge_webserver_internal.sh
