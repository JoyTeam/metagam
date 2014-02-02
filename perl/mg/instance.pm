package mg::instance;

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
