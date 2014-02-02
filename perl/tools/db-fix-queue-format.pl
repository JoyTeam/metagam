#!/usr/bin/perl

# This file is a part of Metagam project.
#
# Metagam is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
# 
# Metagam is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with Metagam.  If not, see <http://www.gnu.org/licenses/>.

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
