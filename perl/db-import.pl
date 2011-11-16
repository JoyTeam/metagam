#!/usr/bin/perl

use strict;
use utf8;
use lib ($0 =~ /(.*)\//) ? $1 : '.';

use mg::instance;
use Data::Dumper;
use JSON;

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

use Encode;

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

sub config
{
	my $inst = shift;
	my $ent = shift;
	my $json = JSON->new->canonical;
	while (my ($grp, $values) = each %{$ent->{config}}) {
		$values = $json->encode($values);
		my ($last_values) = $db->selectrow_array('select `values` from `config` where app=? and grp=? order by stored desc limit 1', undef, $ent->{app}, $grp);
		$last_values = Encode::decode('utf-8', $last_values) if $last_values;
		if ($last_values ne $values) {
			$db->do('insert into `config`(app, stored, grp, `values`) values (?, ?, ?, ?)', undef, $ent->{app}, $ent->{stored}, $grp, $values);
		}
	}
}

sub inventory_stats
{
	my $inst = shift;
	my $ent = shift;
	my $db = $inst->sql->{dbh};
	$db->do('delete from item_remains where app=? and period>=?', undef, $ent->{app}, $ent->{date});
	$db->do('delete from item_descriptions where app=? and period>=?', undef, $ent->{app}, $ent->{date});
	if ($ent->{remains}) {
		# storing remains
		while (my ($item_type, $quantity) = each %{$ent->{remains}}) {
			$db->do('insert into item_remains(app, period, item_type, quantity) values (?, ?, ?, ?)', undef, $ent->{app}, $ent->{date}, $item_type, $quantity);
		}
	} else {
		# loading old remains incrementally
		my %remains;
		if (my ($prev_date) = $db->selectrow_array('select max(period) from item_remains where app=?', undef, $ent->{app})) {
			for my $row (@{$db->selectall_arrayref('select item_type, quantity from item_remains where app=? and period=?', undef, $ent->{app}, $prev_date)}) {
				$remains{$row->{item_type}} = $row->{quantity};
			}
		}
		# updating remains
		while (my ($item_type, $quantity) = each %{$ent->{total}}) {
			$remains{$item_type} += $quantity;
		}
		# storing remains
		while (my ($item_type, $quantity) = each %remains) {
			next if $quantity <= 0;
			$db->do('insert into item_remains(app, period, item_type, quantity) values (?, ?, ?, ?)', undef, $ent->{app}, $ent->{date}, $item_type, $quantity);
		}
	}
	# storing descriptions
	while (my ($description, $hsh) = each %{$ent->{descriptions}}) {
		while (my ($item_type, $quantity) = each %$hsh) {
			next unless $quantity;
			$db->do('insert into item_descriptions(app, period, item_type, description, quantity) values (?, ?, ?, ?, ?)', undef, $ent->{app}, $ent->{date}, $item_type, $description, $quantity);
		}
	}
}

sub money_stats
{
	my $inst = shift;
	my $ent = shift;
	my $db = $inst->sql->{dbh};
	$db->do('delete from money_remains where app=? and period>=?', undef, $ent->{app}, $ent->{date});
	$db->do('delete from money_descriptions where app=? and period>=?', undef, $ent->{app}, $ent->{date});
	if ($ent->{remains}) {
		# storing remains
		while (my ($currency, $amount) = each %{$ent->{remains}}) {
			$db->do('insert into money_remains(app, period, currency, amount) values (?, ?, ?, ?)', undef, $ent->{app}, $ent->{date}, $currency, $amount);
		}
	} else {
		# loading old remains incrementally
		my %remains;
		if (my ($prev_date) = $db->selectrow_array('select max(period) from money_remains where app=?', undef, $ent->{app})) {
			for my $row (@{$db->selectall_arrayref('select currency, amount from money_remains where app=? and period=?', undef, $ent->{app}, $prev_date)}) {
				$remains{$row->{currency}} = $row->{amount};
			}
		}
		# updating remains
		while (my ($currency, $amount) = each %{$ent->{total}}) {
			$remains{$currency} += $amount;
		}
		# storing remains
		while (my ($currency, $amount) = each %remains) {
			next if $amount <= 0;
			$db->do('insert into money_remains(app, period, currency, amount) values (?, ?, ?, ?)', undef, $ent->{app}, $ent->{date}, $currency, $amount);
		}
	}
	# storing descriptions
	while (my ($description, $hsh) = each %{$ent->{descriptions}}) {
		while (my ($currency, $amount) = each %$hsh) {
			next unless $amount;
			$db->do('insert into money_descriptions(app, period, currency, description, amount) values (?, ?, ?, ?, ?)', undef, $ent->{app}, $ent->{date}, $currency, $description, $amount);
		}
	}
}

