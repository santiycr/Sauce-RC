from common import gen_wrappers
from urllib2 import urlopen
from controller.server import load_settings
from nose.tools import with_setup

port = load_settings("allmodes")["port"]

@with_setup(*gen_wrappers("proxy.py",
                          "http://localhost:%s/ping" % port,
                         args=["-p", str(port), "{\"I'm working JSON\": \"yup\"}"]))
def test_ping():
    out = urlopen("http://localhost:%s/ping" % port).read().strip()
    assert out == "pong", "bad output - %s" % out

