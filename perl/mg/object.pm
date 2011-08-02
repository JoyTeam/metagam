package mg::object;

use utf8;
use strict;

sub new
{
	my $class = shift;
	my $inst = shift;
	my $self = {
		inst => $inst,
	};
	bless $self, $class;
	return $self;
}

sub conf
{
	my $self = shift;
	return $self->{inst}->conf->get(@_);
}

sub json_get
{
	my $self = shift;
	return $self->{inst}->json->get(@_);
}

sub json_post
{
	my $self = shift;
	return $self->{inst}->json->post(@_);
}

1;

