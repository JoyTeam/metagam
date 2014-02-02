#!/usr/bin/perl

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

use strict;
use utf8;
use lib ($0 =~ /(.*)\//) ? $1 : '.';

use mg::instance;
use List::Util qw(shuffle);
use POSIX qw(ctime);
use LWP::UserAgent;

my $inst = mg::instance->new;

while (1) {
    sleep 15 + int(rand(5));

    # Load list of running instances
    my $ip = $inst->conf->lget('global', 'addr') or die "global.addr not specified in metagam.conf\n";
    my $daemons = $inst->json->get("http://$ip:4000/core/daemons");
    my %metagam_ips;
    while (my ($srvid, $srvinfo) = each %$daemons) {
        while (my ($svcid, $svcinfo) = each %{$srvinfo->{services}}) {
            if ($svcinfo->{webbackend} eq 'metagam') {
                $metagam_ips{$srvinfo->{addr}} = 1;
            }
        }
    }

    # Prepare list of substitution ips
    my @metagam_ips = shuffle(keys %metagam_ips);

    # Load hetzner failover
    my $hetzner_user = $inst->conf->get('hetzner_user') or die "Hetzner username not configured";
    my $hetzner_pass = $inst->conf->get('hetzner_pass') or die "Hetzner pass not configured";
    my $hetzner_ips = $inst->conf->get('hetzner_ips') or die "Hetzner failover ips not configured";
    my $failover_state = $inst->json->get("https://robot-ws.your-server.de/failover", user => $hetzner_user, pass => $hetzner_pass);

    for my $failover (@{$failover_state}) {
        my $failover = $failover->{failover} or next;
        next if $metagam_ips{$failover->{active_server_ip}};
        my $remap_ip = shift @metagam_ips;
        push @metagam_ips, $remap_ip;
        my $time = ctime(time);
        chomp $time;
        print "$time\tIP $failover->{ip} mapped to offline server $failover->{active_server_ip}. Remapping to $remap_ip: ";
        my $ua = LWP::UserAgent->new;
        my $res = $ua->post("https://robot-ws.your-server.de/failover/$failover->{ip}", {
            active_server_ip => $remap_ip
        }, $inst->json->header(user => $hetzner_user, pass => $hetzner_pass));
        if ($res->is_success) {
            print "OK\n";
        } else {
            my $json;
            eval {
                local $SIG{__DIE__};
                $json = decode_json($res->content);
            };
            if ($json && $json->{error}) {
                print $json->{error}->{code} . "\n";
            } else {
                print $res->status_line . "\n";
            }
        }
    }
}
