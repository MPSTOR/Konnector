# -*- coding: utf-8 -*-
# Michael Breen
# Copyright (C) 2013, 2014, 2015 MPSTOR mpstor.com

from contextlib import contextmanager
import time

class Call(object):
    """Record of a function call, including arguments.
    """
    def __init__(self, func, *args, **dct):
        self.func = func
        self.args = args
        self.dct = dct

    def __call__(self):
        self.func(*self.args, **self.dct)

    def __repr__(self):
        args = [self.func.__name__] + [repr(a) for a in self.args]
        args += ["%s=%r" % (k, v) for k, v in self.dct.items()]
        return 'Call(' + ", ".join(args) + ')'

    def __str__(self):
        args = [repr(a) for a in self.args]
        args += ["%s=%r" % (k, v) for k, v in self.dct.items()]
        return self.func.__name__ + '(' + ", ".join(args) + ')'


def uniq(lst):
    """return a copy of a list of hashable elements, omitting duplicates"""
    _set = {}
    return [_set.setdefault(e, e) for e in lst if e not in _set]


@contextmanager
def timed(seconds=None):
    """Increments seconds[0] by the execution time of the code in context.
    If no seconds list is passed in, a new list [0] is used.
    """
    if seconds is None:
        seconds = [0]
    start = time.time()
    yield seconds
    seconds[0] += time.time() - start


# Might have used Google's ipaddr library instead of the following functions.
# However, ip_on_network() had been written earlier for a driver and not much
# code needed to be added for the others, so I chose to avoid the dependency.


def cidr_to_net_mask(cidr):
    """Convert, e.g., '191.0.219.63/20' to ('191.0.208.0', '255.255.240.0').
    Raises an Exception if cidr is not a valid IPv4 network in CIDR format.
    """
    try:
        net, bits = cidr.split('/')
        check_ip_quads(net)
        mask = bits_to_netmask(int(bits))
        return ip_on_network('0.0.0.0', net, mask), mask
    except:
        raise Exception("Invalid IPv4 CIDR '%s'." % cidr)


def check_ip_quads(addr):
    """Raises an Exception if the argument is not in the form 'A.B.C.D'
    where each of A, B, C, D are integers in the range 0..255.
    """
    try:
        quads = addr.split('.')
        if len(quads) != 4:
            raise Exception()
        for quad in [int(x) for x in quads]:
            if quad > 255 or quad < 0:
                raise Exception()
    except:
        raise Exception("Invalid IPv4 address/mask: '%s'" % addr)


def bits_to_netmask(bits):
    """Given an integer, e.g., 20, returns a netmask, e.g., '255.255..0'.
    Raises an exception if the argument is not an integer in the range 0..32.
    """
    try:
        bits = int(bits)
        if bits < 0 or bits > 32:
            raise Exception()
        quads = [0] * 4
        quads[:bits/8] = [255] * (bits/8)
        if bits % 8:
            quads[bits/8] = 255<<(8 - bits%8) & 255
        return '.'.join([str(x) for x in quads])
    except:
        raise Exception("Network bits must be integer from 0 to 32, not %s."
                % bits)


def ip_on_network(ip, net_ip, net_mask):
    """Changes an IP to the corresponding IP on another network,
    by changing only the bits in the net_mask. For example,
    ip_on_network(ip="1.2.3.4", net_ip="99.88.77.66", net_mask="255.255.0.0")
    returns "99.88.3.4".
    Does no explicit validation of the arguments passed to it.
    """
    return ".".join([str(i & ~m | n & m) for (i, m, n) in
            zip(*[[int(b) for b in s.split(".")] for s in
            (ip, net_mask, net_ip)])])
