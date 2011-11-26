#!/bin/sh
for srv in bind9 cassandra nginx memcached realplexor ; do
	/etc/init.d/$srv start
done
echo "nameserver 127.0.0.1" > /etc/resolv.conf
