from threading import Thread
import sys

def is_frozen():
    return hasattr(sys, "frozen")

def daemon_thread(func, *args):
    t = Thread(target=func, args=args)
    t.daemon = 1
    t.start()
