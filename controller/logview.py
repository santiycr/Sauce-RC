#!/usr/bin/env python

from __future__ import with_statement
from time import time
from threading import Lock
from bisect import bisect

LINES = []
TIMES = []
LOCK = Lock()
MIN_SIZE = 10000
MAX_SIZE = 2 * MIN_SIZE

def locked(fn):
    def wrapper(*args, **kw):
        with LOCK:
            return fn(*args, **kw)
    return wrapper

def trim():
    last = len(LINES) - MIN_SIZE
    del LINES[:last]
    del TIMES[:last]

@locked
def add_line(line):
    now = time()
    LINES.append(line)
    TIMES.append(now)
    if len(LINES) >= MAX_SIZE:
        trim()

@locked
def get_lines(last):
    if not LINES:
        return [], time()
    index = bisect(TIMES, last)
    return LINES[index:], TIMES[-1]
