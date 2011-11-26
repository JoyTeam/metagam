#!/bin/sh
for srv in cassandra nginx memcached realplexor ; do
	/etc/init.d/$srv stop
done
