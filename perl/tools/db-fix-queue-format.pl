#!/usr/bin/perl

use strict;
use utf8;
use lib ($0 =~ /(.*)\//) ? $1 . '/..' : '..';

use mg::instance;

my $inst = mg::instance->new;
my $db = $inst->sql->{dbh};

for my $row (@{$db->selectall_arrayref('select id, data from queue_tasks where cls is null', {Slice=>{}})}) {

    my $data = $inst->json->decode($row->{data});
    my $hook = $data->{hook};
    my $cls = $data->{cls};
    my $args = $inst->json->encode($data->{args});

    print "$row->{id}  $cls  $hook  $args\n";

    $db->do('update queue_tasks set cls=?, hook=?, data=? where id=?', undef, $cls, $hook, $args, $row->{id});
}
