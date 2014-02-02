package mg::cluster;

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
