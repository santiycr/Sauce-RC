#!/usr/bin/env python

from os.path import join
from fnmatch import fnmatch
from os import remove, walk


def clean():
    for root, dirs, files in walk("."):
        for filename in [f for f in files if fnmatch(f, "*.py[co]")]:
            path = join(root, filename)
            print path
            remove(path)

if __name__ == "__main__":
    clean()

