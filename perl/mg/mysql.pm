package mg::mysql;

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

use utf8;
use strict;
use mg::object;
use DBI;
use Carp;

our @ISA = qw(mg::object);

sub new
{
	my $self = mg::object::new(splice @_, 0, 2);
	$self->connect;
	return $self;
}

sub connect
{
	my $self = shift;
	my $host = $self->conf('mysql_write_server')->[0];
	my $database = $self->conf('mysql_database');
	my $user = $self->conf('mysql_user');
	my $password = $self->conf('mysql_password');
	$self->{dbh} = DBI->connect("DBI:mysql:database=$database;host=$host;mysql_client_found_rows=0;mysql_enable_utf8=1", $user, $password, {
		PrintError => 0,
		RaiseError => 1,
		AutoCommit => 1,
		ShowErrorStatement => 1,
		HandleError => sub {
			croak("Database error: " . shift());
		},
	});
}

1;
