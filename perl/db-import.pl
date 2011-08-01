#!/usr/bin/perl

use strict;
use utf8;
use lib ($0 =~ /(.*)\//) ? $1 : '.';

use mg::instance;
use Data::Dumper;

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
		my $handler = "handlers::$ent->{type}";
		unless (defined &{$handler}) {
			local $Data::Dumper::Indent = 0;
			die "Unknown DBExport $ent->{type}: " . Dumper($ent) . "\n";
		}
		$handler->($inst, $ent);
	}

	# deleting processed records
	my @uuids = map { $_->{uuid} } @$lst;
	my $res = $inst->cluster->post($worker, '/dbexport/delete', {uuids => join(',', @uuids)});
}

package handlers;

use Data::Dumper;

sub test
{
	my $inst = shift;
	my $ent = shift;

	print "storing test\n";
}

