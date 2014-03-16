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
use lib ($0 =~ /(.*)\//) ? $1 : '.';
use mg::instance;

my $inst = mg::instance->new;

our (@sql_other, @sql_create_index, @sql_drop_index, @sql_create_foreign_key, @sql_drop_foreign_key, %sql_tables, @sql_create_fields);
our $db = $inst->sql->{dbh};

sql_init();
sql_table('donate',
	[
                'id' => [ -type=>'integer', -null=>0, -key=>'PRI', -extra=>'auto_increment' ],
		'app' => [ -type=>'varchar(32)', -null=>0 ],
		'period' => [ -type=>'date', -null=>0 ],
		'income_cnt' => [ -type=>'integer', -null=>0 ],
		'income_amount' => [ -type=>'decimal(16,2)', -null=>0 ],
		'chargebacks_cnt' => [ -type=>'integer', -null=>0 ],
		'chargebacks_amount' => [ -type=>'decimal(16,2)', -null=>0 ],
	], [
		'index' => 'app,period',
	]
);
sql_table('donators',
	[
                'id' => [ -type=>'integer', -null=>0, -key=>'PRI', -extra=>'auto_increment' ],
		'app' => [ -type=>'varchar(32)', -null=>0 ],
		'period' => [ -type=>'date', -null=>0 ],
		'user' => [ -type=>'varchar(32)', -null=>0 ],
		'income_cnt' => [ -type=>'integer', -null=>0 ],
		'income_amount' => [ -type=>'decimal(16,2)', -null=>0 ],
		'chargebacks_cnt' => [ -type=>'integer', -null=>0 ],
		'chargebacks_amount' => [ -type=>'decimal(16,2)', -null=>0 ],
	], [
		'index' => 'app,period,user',
	]
);
sql_table('visits',
	[
                'id' => [ -type=>'integer', -null=>0, -key=>'PRI', -extra=>'auto_increment' ],
		'app' => [ -type=>'varchar(32)', -null=>0 ],
		'period' => [ -type=>'date', -null=>0 ],
		'peak_ccu' => [ -type=>'integer', -null=>0 ],
		'ccu_dist' => [ -type=>'varchar(150)', -null=>0 ],
		'new_users' => [ -type=>'integer', -null=>0 ],
		'registered' => [ -type=>'integer', -null=>0 ],
		'returned' => [ -type=>'integer', -null=>0 ],
		'abandoned' => [ -type=>'integer', -null=>0 ],
		'active' => [ -type=>'integer', -null=>0 ],
		'dau' => [ -type=>'integer', -null=>0 ],
		'wau' => [ -type=>'integer', -null=>0 ],
		'mau' => [ -type=>'integer', -null=>0 ],
	], [
		'index' => 'app,period',
	]
);
sql_table('active_players',
	[
                'id' => [ -type=>'integer', -null=>0, -key=>'PRI', -extra=>'auto_increment' ],
		'app' => [ -type=>'varchar(32)', -null=>0 ],
		'period' => [ -type=>'date', -null=>0 ],
		'player' => [ -type=>'varchar(32)', -null=>0 ],
		'online' => [ -type=>'integer', -null=>0 ],
	], [
		'index' => 'app,period',
		'index' => 'period',
	]
);
sql_table('config',
	[
                'id' => [ -type=>'integer', -null=>0, -key=>'PRI', -extra=>'auto_increment' ],
		'app' => [ -type=>'varchar(32)', -null=>0 ],
		'stored' => [ -type=>'datetime', -null=>0 ],
		'grp' => [ -type=>'varchar(50)', -null=>0 ],
		'values' => [ -type=>'text', -null=>0 ],
	], [
		'index' => 'app,stored',
		'index' => 'app,grp,stored',
	]
);
sql_table('item_remains',
	[
                'id' => [ -type=>'integer', -null=>0, -key=>'PRI', -extra=>'auto_increment' ],
		'app' => [ -type=>'varchar(32)', -null=>0 ],
		'period' => [ -type=>'date', -null=>0 ],
		'item_type' => [ -type=>'varchar(32)', -null=>0 ],
		'quantity' => [ -type=>'integer', -null=>0 ],
	], [
		'index' => 'app,period',
		'index' => 'app,item_type,period',
	]
);
sql_table('item_descriptions',
	[
                'id' => [ -type=>'integer', -null=>0, -key=>'PRI', -extra=>'auto_increment' ],
		'app' => [ -type=>'varchar(32)', -null=>0 ],
		'period' => [ -type=>'date', -null=>0 ],
		'item_type' => [ -type=>'varchar(32)', -null=>0 ],
		'description' => [ -type=>'varchar(32)', -null=>0 ],
		'quantity' => [ -type=>'integer', -null=>0 ],
	], [
		'index' => 'app,period',
		'index' => 'app,item_type,period',
		'index' => 'app,description,period',
		'index' => 'app,item_type,description,period',
	]
);
sql_table('money_remains',
	[
                'id' => [ -type=>'integer', -null=>0, -key=>'PRI', -extra=>'auto_increment' ],
		'app' => [ -type=>'varchar(32)', -null=>0 ],
		'period' => [ -type=>'date', -null=>0 ],
		'currency' => [ -type=>'varchar(10)', -null=>0 ],
		'amount' => [ -type=>'decimal(16,2)', -null=>0, -default=>'0.00' ],
	], [
		'index' => 'app,period',
		'index' => 'app,currency,period',
	]
);
sql_table('money_descriptions',
	[
                'id' => [ -type=>'integer', -null=>0, -key=>'PRI', -extra=>'auto_increment' ],
		'app' => [ -type=>'varchar(32)', -null=>0 ],
		'period' => [ -type=>'date', -null=>0 ],
		'currency' => [ -type=>'varchar(10)', -null=>0 ],
		'description' => [ -type=>'varchar(32)', -null=>0 ],
		'amount' => [ -type=>'decimal(16,2)', -null=>0, -default=>'0.00' ],
	], [
		'index' => 'app,period',
		'index' => 'app,currency,period',
		'index' => 'app,description,period',
		'index' => 'app,currency,description,period',
	]
);
sql_table('queue_tasks',
	[
                'idn' => [ -type=>'integer', -null=>0, -key=>'PRI', -extra=>'auto_increment' ],
		'id' => [ -type=>'varchar(32)', -null=>0 ],
                'cls' => [ -type=>'varchar(16)', -null=>1 ],
		'app' => [ -type=>'varchar(32)', -null=>0 ],
		'at' => [ -type=>'datetime', -null=>0 ],
		'priority' => [ -type=>'integer', -null=>0 ],
		'unique' => [ -type=>'varchar(84)', -null=>1 ],
                'hook' => [ -type=>'varchar(32)', -null=>0 ],
		'data' => [ -type=>'longblob' ],
		'locked' => [ -type=>'varchar(50)', -null=>0 ],
		'locked_till' => [ -type=>'datetime', -null=>1 ],
	], [
		'index' => 'id',
		'index' => 'app,unique',
		'index' => 'cls,locked,at',
		'index' => 'cls,locked_till',
	]
);
sql_table('modifiers',
	[
                'id' => [ -type=>'integer', -null=>0, -key=>'PRI', -extra=>'auto_increment' ],
		'till' => [ -type=>'datetime', -null=>0 ],
		'cls' => [ -type=>'varchar(16)' ],
		'app' => [ -type=>'varchar(32)' ],
		'target_type' => [ -type=>'varchar(16)' ],
		'target' => [ -type=>'varchar(32)' ],
		'priority' => [ -type=>'integer', -null=>0, -default=>'100' ],
	], [
		'index' => 'app,target,till',
		'index' => 'cls,till',
	]
);
sql_table('shops_sell',
	[
                'id' => [ -type=>'integer', -null=>0, -key=>'PRI', -extra=>'auto_increment' ],
		'app' => [ -type=>'varchar(32)', -null=>0 ],
		'shop' => [ -type=>'varchar(80)', -null=>0 ],
		'item_type' => [ -type=>'varchar(32)', -null=>0 ],
		'period' => [ -type=>'date', -null=>0 ],
		'currency' => [ -type=>'varchar(10)', -null=>0 ],
		'amount' => [ -type=>'decimal(16,2)', -null=>0, -default=>'0.00' ],
		'quantity' => [ -type=>'integer', -null=>0 ],
	], [
		'index' => 'app,period,currency',
		'index' => 'app,shop,period',
		'index' => 'app,item_type,period',
		'index' => 'app,shop,item_type,period',
	]
);
sql_table('shops_buy',
        [
                'id' => [ -type=>'integer', -null=>0, -key=>'PRI', -extra=>'auto_increment' ],
                'app' => [ -type=>'varchar(32)', -null=>0 ],
                'shop' => [ -type=>'varchar(80)', -null=>0 ],
                'item_type' => [ -type=>'varchar(32)', -null=>0 ],
                'period' => [ -type=>'date', -null=>0 ],
                'currency' => [ -type=>'varchar(10)', -null=>0 ],
                'amount' => [ -type=>'decimal(16,2)', -null=>0, -default=>'0.00' ],
                'quantity' => [ -type=>'integer', -null=>0 ],
        ], [
                'index' => 'app,period,currency',
                'index' => 'app,shop,period',
                'index' => 'app,item_type,period',
                'index' => 'app,shop,item_type,period',
        ]
);
sql_table('crafting_daily',
        [
                'id' => [ -type=>'integer', -null=>0, -key=>'PRI', -extra=>'auto_increment' ],
                'app' => [ -type=>'varchar(32)', -null=>0 ],
                'period' => [ -type=>'date', -null=>0 ],
                'recipe' => [ -type=>'varchar(32)', -null=>0 ],
                'quantity' => [ -type=>'integer', -null=>0 ],
        ], [
                'index' => 'app,period',
                'index' => 'app,recipe',
        ]
);
sql_table('crafting_daily_param1',
	[
                'id' => [ -type=>'integer', -null=>0, -key=>'PRI', -extra=>'auto_increment' ],
		'app' => [ -type=>'varchar(32)', -null=>0 ],
		'param1' => [ -type=>'varchar(32)', -null=>0 ],
		'period' => [ -type=>'date', -null=>0 ],
		'recipe' => [ -type=>'varchar(32)', -null=>0 ],
                'param1val' => [ -type=>'integer', -null=>0 ],
		'quantity' => [ -type=>'integer', -null=>0 ],
	], [
		'index' => 'app,param1,period,param1val',
		'index' => 'app,param1,recipe,param1val',
	]
);
sql_done();

sub sql_field
{
	my $sql_table = shift;
	my $sql_fields = shift;
	my $sql_unikeys = shift;
	my $sql_field = shift;

	my ($sql_type, $sql_null, $sql_key, $sql_extra, $sql_default);

	$sql_null = 1;

	while ($#_ >= 1) {

		my $type = shift;
		my $value = shift;

		if ($type eq '-type') {

			$sql_type = $value;

			if ($sql_type eq 'integer') {
				$sql_type = 'int(11)';
			} elsif ($sql_type eq 'bool') {
				$sql_type = 'tinyint(1)';
			}
			
		} elsif ($type eq '-null') {

			$sql_null = $value;

		} elsif ($type eq '-default') {

			$sql_default = $value;

		} elsif ($type eq '-key') {

			$sql_key = $value;
			$sql_unikeys->{$sql_field} = 1;			

		} elsif ($type eq '-extra') {

			$sql_extra = $value;

		} else {

			die "SQL field $sql_table.$sql_field constructor error: unknown argument $type\n";
		}
	}

	if ($#_ >= 0) {
	
		die "SQL field constructor error: not paired argument '$_[0]'\n";
	}

	my $found = 0;

	my $new_def = &sql_field_def($sql_field, $sql_type, $sql_null, $sql_key, $sql_default, $sql_extra);

	if ($sql_table) {

		my $q = $db->prepare("show fields from $sql_table");
		$q->execute;
		
		while (my ($cur_field, $cur_type, $cur_null, $cur_key, $cur_default, $cur_extra) = $q->fetchrow_array) {

			$cur_null = undef if $cur_null eq 'NO';

			if ($cur_field eq $sql_field) {

				my $cur_def = &sql_field_def($cur_field, $cur_type, $cur_null, $cur_key, $cur_default, $cur_extra);

				if ($new_def ne $cur_def) {
					
					$new_def =~ s/ primary key//;

					push @sql_other, "alter table $sql_table modify column $new_def";
				
				}

				$sql_fields->{$sql_field} = 0;

				$found = 1;
				last;
			}
			
		}
		
		if (!$found) {

			push @sql_other, "alter table $sql_table add column $new_def";
		
		}
		
	} else {
	
		push @sql_create_fields, $new_def;
	}
}

sub sql_init
{
	@sql_other = ();
	@sql_create_index = ();
	@sql_drop_index = ();
	@sql_create_foreign_key = ();
	@sql_drop_foreign_key = ();
	@sql_create_fields = ();
	%sql_tables = ();
}

sub sql_done
{
	my $q = $db->prepare('show tables');
	$q->execute;

	while (my ($existing_table) = $q->fetchrow_array) {

		unless ($sql_tables{$existing_table}) {

			push @sql_other, "drop table $existing_table" unless $existing_table =~ /^ipbdb/;
		}
	}

	for my $command (@sql_drop_foreign_key, @sql_drop_index, @sql_other, @sql_create_index, @sql_create_foreign_key) {

		print "MYSQL: $command\n";
		$db->do($command);
	}
}

sub sql_table
{
	my ($sql_table, $sql_fields, $sql_constraints, $sql_options) = @_;

	$sql_tables{$sql_table} = 1;

	my $q = $db->prepare('show tables');
	$q->execute;

	my $found = 0;

	while (my ($existing_table) = $q->fetchrow_array) {

		if ($existing_table eq $sql_table) {

			$found = 1;
			last;
		
		}
	
	}

	my %unikey = ();
	
	my %sql_fields = ();
	my $sql_cr;

	if (!$found) {
	
		$sql_cr = 1;
		@sql_create_fields = ();
		
	} else {

		my $q = $db->prepare("show fields from $sql_table");
		$q->execute;
		
		while (my ($field) = $q->fetchrow_array) {
		
			$sql_fields{$field} = 1;
			
		}

		$sql_cr = 0;
	}

	for (my $i = 0; $i < @$sql_fields; $i += 2) {

		my $name = $sql_fields->[$i];
		my $options = $sql_fields->[$i + 1];

		&sql_field(($sql_cr ? '' : $sql_table), \%sql_fields, \%unikey, $name, @$options);
	}

	if ($sql_cr) {

		push @sql_other, "create table $sql_table (" . (join ', ', @sql_create_fields) . ') engine=' . ($sql_options->{engine} || 'innodb') . ' default charset utf8';
	
	} else {

		for my $field (keys %sql_fields) {

			if ($sql_fields{$field}) {
				
				push @sql_other, "alter table $sql_table drop column `$field`";
			}			
		}		
	}

	my %existing_indexes = ();
	my %existing_unikeys = ();
	my %existing_fk = ();
	my %fk_real_name = ();

	if (!$sql_cr) {

		my $q = $db->prepare("show create table $sql_table");
		$q->execute;
		my (undef, $create) = $q->fetchrow_array;

		for (split /\n/, $create) {

			if (/UNIQUE KEY \`(\S+)\`\s*\(\`\S+\`\)/) {

				$existing_unikeys{$1} = 1;
				
			} elsif (/KEY \`(\S+)\`\s*\(\`\S+\`\)/) {

				$existing_indexes{$1} = 1;
				
			} elsif (/CONSTRAINT \`(\S+)\`\s*FOREIGN KEY\s*\(\`(\S+)\`\)\s*REFERENCES\s*\`(\S+)\`\s*\(\`(\S+)\`\)/) {

				my $fk_name = $sql_table . '_' . $2 . '_' . $3 . '_' . $4;
				$fk_real_name{$fk_name} = $1;

				$existing_fk{$fk_name} = 1;
			}
		}
	}

	for (my $i = 0; $i < @$sql_constraints; $i += 2) {

		my $type = $sql_constraints->[$i];
		my $options = $sql_constraints->[$i + 1];

		if ($type eq 'index') {

			my $field = $options;

			my $index_name = $sql_table . '_'  . $field;

			$index_name =~ s/,/_/g;

			$field =~ s/,/`,`/g;

			push @sql_create_index, "create index $index_name on $sql_table(`$field`)" unless $existing_indexes{$index_name};
			delete $existing_indexes{$index_name};

		} elsif ($type eq 'fk') {

			my ($field, $parent, $parent_key) = @$options;

			my $fk_name = $sql_table . '_' . $field . '_' . $parent . '_' . $parent_key;

			push @sql_create_foreign_key, "alter table $sql_table add foreign key $fk_name($field) references $parent($parent_key)" unless $existing_fk{$fk_name};
			delete $existing_fk{$fk_name};
		}
	}

	for my $index (keys %existing_indexes) {

		push @sql_drop_index, "alter table $sql_table drop index $index";
	}
	
	for my $fk_name (keys %existing_fk) {

		push @sql_drop_foreign_key, "alter table $sql_table drop foreign key $fk_real_name{$fk_name}";
	}
	
	for my $key (keys %existing_unikeys) {

		push @sql_drop_index, "alter table $sql_table drop index $key" unless $unikey{$key};
	}
}

sub sql_field_def
{
	my ($field, $type, $null, $key, $default, $extra) = @_;

	$type =~ s/varchar/char/;
	$null = ($extra =~ /auto_increment/) ? '' : ($null ? 'null' : 'not null');
	$key = ($key eq 'PRI') ? 'primary key' : ($key eq 'UNI') ? 'unique' : '';

	$default = (defined $default) ? "default '$default'" : 'default null';

	if ($null eq 'not null' && $default eq 'default null') {
		if ($type =~ /int/) {
			$default = "default '0'";
		} elsif ($type eq 'datetime') {
			$default = "default '0000-00-00 00:00:00'";
		} elsif ($type eq 'date') {
			$default = "default '0000-00-00'";
		} elsif (my ($prec) = ($type =~ /^decimal\(\d+,(\d+)\)$/)) {
			$default = sprintf "default '%.${prec}f'", 0;
		} else {
			$default = "default ''";
		}
	}

	my $res = "`$field` $type $null $key $default $extra";
	$res =~ s/\s+/ /g;
	$res =~ s/^\s*(.*?)\s*$/$1/;
	return $res;
}
