package mg::conf;

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

our @ISA = qw(mg::object);

sub new
{
    my $self = mg::object::new(splice @_, 0, 2);
    $self->{ldata} = {};
    my $file = $self->{conffile} = '/etc/metagam/metagam.conf';
    open my $f, '<', $file or die "Could not open $file: $!\n";
    my $group;
    while (my $line = <$f>) {
        $line =~ s/^\s*(.*?)\s*$/$1/s;
        if (my ($g) = $line =~ /^\[(.*?)\]$/) {
            $group = $g;
        } elsif (my ($key, $value) = $line =~ /^(.+?)\s*:\s*(.*?)$/) {
            $self->{ldata}->{$group}->{$key} = $value;
        }
    }
    close $f;
    $self->{ip} = $self->{ldata}->{global}->{addr} or die "global.addr not specified in $self->{conffile}\n";
    $self->{data} = $self->json_get("http://$self->{ip}:4000/core/config");
    $self->{data}->{ip} = $self->{ip};
    return $self;
}

sub lget
{
    my $self = shift;
    my $group = shift;
    my $key = shift;
    return $self->{ldata}->{$group}->{$key};
}

sub get
{
    my $self = shift;
    my $key = shift;
    return $self->{data}->{$key};
}

1;
