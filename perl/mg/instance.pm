package mg::instance;

use utf8;
use strict;

use mg::mysql;
use mg::conf;
use mg::json;
use mg::cluster;

sub new
{
	return bless {}, shift;
}

sub conf
{
	my $self = shift;
	return $self->{conf} ||= mg::conf->new($self);
}

sub sql
{
	my $self = shift;
	return $self->{sql} ||= mg::mysql->new($self);
}

sub json
{
	my $self = shift;
	return $self->{json} ||= mg::json->new($self);
}

sub cluster
{
	my $self = shift;
	return $self->{cluster} ||= mg::cluster->new($self);
}

1;
