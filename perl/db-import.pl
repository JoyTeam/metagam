#!/usr/bin/perl

use strict;
use utf8;
use lib ($0 =~ /(.*)\//) ? $1 : '.';
use mg::instance;

my $inst = mg::instance->new;
my $sql = $inst->sql->{dbh};
my @workers = $inst->cluster->workers_of_class('metagam') or die "No metagam workers\n";
my $worker = $workers[int(rand(@workers))];

while (1) {
	# loading next bucket of records
	my $lst = $inst->cluster->get($worker, '/dbexport/get');
	last unless @$lst;

	# processing records
	for my $ent (@$lst) {
		no strict 'refs';
		my $handler = \&{"handlers::$ent->{type}"} or die "Unknown DBExport type $ent->{type}\n";
		$handler->($inst, $ent);
	}

	# deleting processed records
	my @uuids = map { $_->{uuid} } @$lst;
	my $res = $inst->cluster->post($worker, '/dbexport/delete', {uuids => join(',', @uuids)});
}

package handlers;

sub test
{
	my $inst = shift;
	my $ent = shift;

	print "storing test\n";
}
