package mg::mysql;

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
	my $host = $self->conf('mysql_write_server');
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
