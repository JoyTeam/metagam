package mg::conf;

use utf8;
use strict;
use mg::object;

our @ISA = qw(mg::object);

sub new
{
	my $self = mg::object::new(splice @_, 0, 2);
	$self->{data} = $self->json_get('http://director:3000/director/config');
	return $self;
}

sub get
{
	my $self = shift;
	my $key = shift;
	return $self->{data}->{$key};
}

1;
