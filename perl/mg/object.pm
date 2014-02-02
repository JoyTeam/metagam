package mg::object;

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

