#!/bin/bash
cd `dirname $0`
num=$(qstat -q continuous | grep celery | wc -l)
./stop_celery.sh
while [ "$(qstat -q continuous | grep celery | wc -l)" -gt 0 ];
do
    sleep 1
done
for i in $(seq 1 ${num});
do
    jstart -N celery${i} -once -continuous -l h_vmem=3G -l release=trusty ./celery.grid.sh $i
    sleep 10
done
