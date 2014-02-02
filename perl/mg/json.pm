package mg::json;

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
use LWP::UserAgent;
use JSON;
use MIME::Base64;

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
    my %options = @_;
    my $ua = LWP::UserAgent->new;
    my $res = $ua->get($uri, $self->header(%options));
    die "Error getting $uri: " . $res->status_line . "\n" unless $res->is_success;
    return decode_json($res->content);
}

sub post
{
    my $self = shift;
    my $uri = shift;
    my $params = shift;
    my %options = @_;
    my $ua = LWP::UserAgent->new;
    my $res = $ua->post($uri, $params, $self->header(%options));
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

sub header
{
    my $self = shift;
    my %options = @_;
    my %result = ();
    if ($options{user}) {
        $result{Authorization} = 'Basic ' . encode_base64($options{user} . ':' . $options{pass}, '');
    }
    return %result;
}

1;

