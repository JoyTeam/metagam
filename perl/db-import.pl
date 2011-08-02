#!/usr/bin/perl

use strict;
use utf8;
use lib ($0 =~ /(.*)\//) ? $1 : '.';

use mg::instance;
use Data::Dumper;

my $inst = mg::instance->new;
my $db = $inst->sql->{dbh};
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

$db->do('delete from active_players where period < date_sub(now(), interval 90 day)');

package handlers;

sub online
{
	my $inst = shift;
	my $ent = shift;
	my $db = $inst->sql->{dbh};
	my $period = $ent->{since};
	$period =~ s/ \d\d:\d\d:\d\d//;
	$db->do('delete from visits where app=? and period=?', undef, $ent->{app}, $period);
	$db->do('delete from active_players where app=? and period=?', undef, $ent->{app}, $period);
	while (my ($player, $online) = each %{$ent->{players}}) {
		$db->do('insert into active_players(app, period, player, online) values (?, ?, ?, ?)', undef, $ent->{app}, $period, $player, $online);
	}
	my ($mau) = $db->selectrow_array('select count(1) from (select player from active_players where app=? and period between date_sub(?, interval 29 day) and ? group by player) apl', undef, $ent->{app}, $period, $period);
	my ($wau) = $db->selectrow_array('select count(1) from (select player from active_players where app=? and period between date_sub(?, interval 6 day) and ? group by player) apl', undef, $ent->{app}, $period, $period);
	my ($dau) = $db->selectrow_array('select count(1) from (select player from active_players where app=? and period=? group by player) apl', undef, $ent->{app}, $period);
	$db->do('insert into visits(app, period, peak_ccu, ccu_dist, new_users, registered, returned, abandoned, active, dau, wau, mau) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', undef, $ent->{app}, $period, $ent->{peak_ccu}, join(',', @{$ent->{ccu_dist}}), $ent->{new_users}, $ent->{registered}, $ent->{returned}, $ent->{left}, $ent->{active}, $dau, $wau, $mau);
}

sub donate
{
	my $inst = shift;
	my $ent = shift;
	my $field = shift || 'income';
	my $db = $inst->sql->{dbh};
	my $period = $ent->{stored};
	$period =~ s/ \d\d:\d\d:\d\d//;
	if ($db->do("update donate set ${field}_cnt=${field}_cnt+1, ${field}_amount=${field}_amount+? where app=? and period=?", undef, $ent->{amount}, $ent->{app}, $period) < 1) {
		$db->do("insert into donate(app, period, ${field}_cnt, ${field}_amount) values (?, ?, 1, ?)", undef, $ent->{app}, $period, $ent->{amount});
	}
	if ($db->do("update donators set ${field}_cnt=${field}_cnt+1, ${field}_amount=${field}_amount+? where app=? and period=? and user=?", undef, $ent->{amount}, $ent->{app}, $period, $ent->{user}) < 1) {
		$db->do("insert into donators(app, period, user, ${field}_cnt, ${field}_amount) values (?, ?, ?, 1, ?)", undef, $ent->{app}, $period, $ent->{user}, $ent->{amount});
	}
}

sub chargeback
{
	my $inst = shift;
	my $ent = shift;
	donate($inst, $ent, 'chargebacks');
}
