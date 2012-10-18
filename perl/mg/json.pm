package mg::json;

use utf8;
use strict;
use mg::object;
use LWP::UserAgent;
use JSON;

our @ISA = qw(mg::object);

sub new
{
	my $self = mg::object::new(splice @_, 0, 2);
	return $self;
}

sub get
{
	my $self = shift;
	my $uri = shift;
	my $ua = LWP::UserAgent->new;
	my $res = $ua->get($uri);
	die "Error getting $uri: " . $res->status_line . "\n" unless $res->is_success;
	return decode_json($res->content);
}

sub post
{
	my $self = shift;
	my $uri = shift;
	my $params = shift;
	my $ua = LWP::UserAgent->new;
	my $res = $ua->post($uri, $params);
	die "Error posting $uri: " . $res->status_line . "\n" unless $res->is_success;
	return decode_json($res->content);
}

sub encode
{
    my $self = shift;
    my $data = shift;
    return encode_json($data);
}

sub decode
{
    my $self = shift;
    my $data = shift;
    return decode_json($data);
}

1;

