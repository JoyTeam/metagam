#!/bin/sh
images=$(cd ../../../mg/data/icons/ ; ls *.png | egrep -v '^chat')
for image in $images ; do
	composite -gravity center ../../../mg/data/icons/$image btn-bg.png $image
done
