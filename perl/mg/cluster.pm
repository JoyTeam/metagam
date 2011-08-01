package mg::cluster;

use utf8;
use strict;
use mg::object;

our @ISA = qw(mg::object);

sub new
{
	my $self = mg::object::new(splice @_, 0, 2);
	return $self;
}

sub workers_of_class
{
	my $self = shift;
	my $class = shift;
	my $servers = $self->json_get('http://director:3000/director/servers');
	my @workers;
	while (my ($server_id, $info) = each %$servers) {
		if ($info->{params}->{class} eq $class) {
			push @workers, {
				id => $server_id,
				host => $info->{host},
				port => $info->{port},
			};
		}
	}
	return @workers;
}

sub get
{
	my $self = shift;
	my $srv = shift;
	my $url = shift;
	return $self->json_get("http://$srv->{host}:$srv->{port}$url");
}

sub post
{
	my $self = shift;
	my $srv = shift;
	my $url = shift;
	my $params = shift;
	return $self->json_post("http://$srv->{host}:$srv->{port}$url", $params);
}

1;
