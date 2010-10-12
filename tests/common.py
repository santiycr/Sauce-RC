from os.path import dirname, join, abspath, isfile
from sys import path, executable, platform
from subprocess import Popen, PIPE
from functools import wraps
from time import sleep, time
from urllib2 import urlopen, URLError

root = dirname(dirname(abspath(__file__)))
path.append(root)

def wait_for_server(url, timeout=5, mintime=1):
    start = time()
    while 1:
        diff = time() - start
        if diff > timeout:
            break
        try:
            urlopen(url)
            if diff > mintime:
                return
            sleep(mintime - diff)
            return
        except URLError:
            sleep(0.1)

def run_script(script, wait_url, args=[]):
    script = join(root, "controller", script)
    assert isfile(script), "can't find %s" % script
    cmd = [executable, script] + args
    pipe = Popen(cmd, cwd=root)
    wait_for_server(wait_url)
    return pipe

def kill_selenium():
    if platform == "win32":
        return # FIXME

    from os import kill, environ
    from signal import SIGTERM, SIGKILL

    for kill_signal in [SIGTERM, SIGKILL]:
        pipe = Popen(["ps", "aux"], stdout=PIPE)
        for line in pipe.stdout:
            if "selenium-server.jar" not in line:
                continue

            fields = line.split()
            user, pid = fields[0], int(fields[1])
            if user != environ["USER"]:
                continue

            kill(pid, kill_signal)

def gen_wrappers(script, wait_url, args=[]):
    # When we'll we get "real" lexical scoping in Python
    f = []

    def setup():
        f.append(run_script(script, wait_url, args))

    def teardown():
        for script in f:
            script.kill()
        kill_selenium()

    return setup, teardown
