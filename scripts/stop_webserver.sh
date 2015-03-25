#!/bin/bash
echo "stopping webserver"
qstat -q webgrid-generic | awk '{ if ($1~/[0-9]+/) cmd="qdel " $1; system(cmd); close(cmd)}'
