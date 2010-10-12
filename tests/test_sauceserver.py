from urllib2 import urlopen
try:
    import json
except ImportError:
    import simplejson as json
from common import gen_wrappers
from nose.tools import with_setup

def call(path, is_json=False):
    fo = urlopen("http://localhost:8421/%s" % path)
    return json.load(fo) if is_json else fo.read()

def status():
    return call("status", True)

@with_setup(*gen_wrappers("server.py", "http://localhost:8421/status"))
def test_start():
    call("start")
    assert status()["running"], "not running"

@with_setup(*gen_wrappers("server.py", "http://localhost:8421/status"))
def test_stop():
    call("stop")
    assert not status()["running"], "not running"
