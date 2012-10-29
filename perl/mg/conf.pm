package mg::conf;

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
}

sub get
{
    my $self = shift;
    my $key = shift;
    return $self->{data}->{$key};
}

1;
