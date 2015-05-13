#!/bin/bash
echo "stopping celery jobs"
qdel -u $USER "celery*"
