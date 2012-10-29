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
        my $ip = $self->conf('ip');
	my $daemons = $self->json_get("http://$ip:4000/core/daemons");
	my @workers;
	while (my ($dmnid, $dmninfo) = each %$daemons) {
            next if $dmninfo->{type} ne $class;
            if ($dmninfo->{services}) {
                while (my ($svcid, $svcinfo) = each %{$dmninfo->{services}}) {
                    next if $svcinfo->{type} ne 'int';
                    push @workers, {
                        id => $svcid,
                        addr => $svcinfo->{addr},
                        port => $svcinfo->{port},
                    };
                }
            }
	}
	return @workers;
}

sub get
{
	my $self = shift;
	my $srv = shift;
	my $url = shift;
	return $self->json_get("http://$srv->{addr}:$srv->{port}$url");
}

sub post
{
	my $self = shift;
	my $srv = shift;
	my $url = shift;
	my $params = shift;
	return $self->json_post("http://$srv->{addr}:$srv->{port}$url", $params);
}

1;
