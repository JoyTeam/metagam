#!/bin/sh

export LC_CTYPE=ru_RU.UTF-8
export HOME=/home/aml
export PYTHONPATH=/home/mg

cd /home/mg

screen -D -S dir -m bin/mg_director
