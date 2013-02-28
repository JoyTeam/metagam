#!/bin/sh

dir=$(dirname $(dirname $(realpath "$0")))
cd $dir

export LC_CTYPE=ru_RU.UTF-8
export HOME=/home/metagam
export PYTHONPATH=$dir

while true ; do
	screen -D -m -S mmoconstructor bin/mg_procman
done
