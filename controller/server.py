#!/usr/bin/env python

from __future__ import with_statement
import version
from env import (
    ID_FILE, RCDIR, USER_CONFIG, DEFAULT_CFG, SELENIUM_JAR, LOG_FILE, JAVA,
    APPDIR, is_frozen, SERVER_PORT, PROXY, BROWSERS_FILE, USER_BROWSERS_FILE,
    CONTROLLER_DIR, ONDEMANDHOST, ONDEMANDPORT, CREATION_FLAGS, TUNNEL,
    TUNNEL_FLAG
)
from common import daemon_thread
from os.path import isfile, isdir, join, devnull

# CherryPy must be in sys.path
import sys; sys.path.append(join(CONTROLLER_DIR, "lib"))
from cherrypy import expose, quickstart
import cherrypy

from urllib2 import urlopen, HTTPError, URLError
from subprocess import Popen, PIPE, STDOUT
try:
    import json
except ImportError:
    import simplejson as json
from time import time, sleep, strftime
from shutil import copy
from os import chdir, mkdir, remove
from sys import platform, executable, stdout
from uuid import uuid4
import logview
import atexit
from log import run_logger, log, start_logging
from cgi import escape
import httplib

VERSION = "%s (build %s)" % (version.version, version.build)
NEW_VERSION = None
ONDEMAND_REACHABLE = True # Be optimistic
HTMLSUITE_RUNNING = False

sever_should_run = True

def check_ondemand():
    global ONDEMAND_REACHABLE

    while True:
        ok = True
        if current_mode == proxy:
            try:
                fo = urlopen("http://%s:%s/status" % (ONDEMANDHOST, ONDEMANDPORT))
                ok = 'OK' in fo.readline()
            except (HTTPError, URLError):
                ok = False

        ONDEMAND_REACHABLE = ok
        sleep(5 * 60) # 2 minutes

def open_browser_when_ready():
        import webbrowser
        url = "http://127.0.0.1:%d" % SERVER_PORT
        for i in range(30):
            try:
                urlopen(url)
                webbrowser.open(url)
                break
            except IOError:
                sleep(1)

def is_new_browsers(browsers):
    with open(USER_BROWSERS_FILE) as fo:
        old = json.load(fo)

    return old != browsers

def get_browsers():
    day = 60 * 60 * 24
    while 1:
        try:
            fo = urlopen("http://saucelabs.com/rest/conf/browsers")
            browsers = json.load(fo)
            if is_new_browsers(browsers):
                with open(USER_BROWSERS_FILE, "w") as fo:
                    json.dump(browsers, fo, indent=4)
        except (HTTPError, URLError, ValueError): # ValueError comes from bad JSON
            pass

        sleep(day)

def get_id():
    id_file = ID_FILE
    try:
        # Create if not there
        if not isfile(id_file):
            with open(id_file, "w") as fo:
                fo.write(uuid4().hex + "\n")

        return open(id_file).read().strip()
    except IOError:
        return "unknown"

def get_last_version(url=None):
    url = url or "http://saucelabs.com/versions.json"
    url = "%s?id=%s" % (url, get_id())
    data = json.load(urlopen(url))
    retval = data["Sauce RC"]
    if platform == "darwin":
        return retval["OS X"]

    retval.pop("OS X", None)
    return retval

def is_new_version(old, new):
    try:
        old = int(old)
        new = int(new)
    except ValueError, e:
        print "ERROR: Bad version - %s" % e
        # FIXME: I'm not sure this is the right thing to do
        return False # Can't compare

    return new > old

def version_thread(onetime=0):
    global NEW_VERSION
    while 1:
        try:
            new_version = get_last_version()
        except (ValueError, HTTPError, URLError): # ValueError comes from bad JSON
            new_version = {"build": -1} # If fails to load from web, assume not new avail

        if is_new_version(version.build, new_version["build"]):
            NEW_VERSION = new_version

        if onetime:
            break
        sleep(60 * 60 * 24)

def ensure_user_config(filename=USER_CONFIG, default=DEFAULT_CFG):
    if not isdir(RCDIR):
        mkdir(RCDIR)

    if not isfile(filename):
        copy(default, filename)
    else: # Check that it's not old config
        try:
            load_config(ensure=0)
        except ValueError:
            save_user_config()
            copy(default, filename)


def load_config(ensure=1):
    if ensure:
        ensure_user_config()
    with open(USER_CONFIG, 'r') as config_file:
        return json.load(config_file)

def save_config(config):
    # "_" is jQuery caching key
    config.pop("_", None)
    with open(USER_CONFIG, 'w') as fo:
        json.dump(config, fo, sort_keys=True, indent=4)

# "ondemand-username" -> "ondemand", "username"
def split_key(key):
    if "-" not in key:
        return "allmodes", key
    return key.split("-", 1)

def load_settings(prefix):
    items = ((split_key(key), value) for key, value in load_config().items())
    def relevant(key):
        return ((key[0] == "allmodes") or (key[0] == prefix))

    return dict((key[1], value) for key, value in items if relevant(key))

def check_ondemand_settings():
    config = load_settings("ondemand")
    return bool(config.get("username") and config.get("access-key"))

def terminate(pipe):
    if hasattr(pipe, "terminate") and hasattr(pipe, "kill"):
        pipe.terminate()
        for _ in range(30):
            if pipe.poll() == None:
                sleep(1)
            else:
                break
        else:
            pipe.kill()
    else:
        # On Windows we're bundling in 2.6, so if we're here we assume it Linux/Mac
        from os import kill
        from signal import SIGTERM, SIGKILL

        kill(pipe.pid, SIGTERM)
        for _ in range(30):
            if pipe.poll() == None:
                sleep(1)
            else:
                break
        else:
            kill(pipe.pid, SIGKILL)

class Server:
    '''Base class for external server process.

    Subclasses should implement get_wait_flag, _command_line and define name
    '''
    name = None
    htmlsuite_running = False
    num_tries_for_ready = 30

    def __init__(self):
        self.server = None

    def start(self, additional_params=None):
        if self.is_running():
            return

        command_line = self._command_line(additional_params)
        for i in self.required_arg:
            if i not in " ".join(command_line):
                log("Sauce RC",
                    "Can't start %s without all the required arguments: %s" % (self.name, ", ".join(self.required_arg)))
                return
        log("Sauce RC",
            "Starting %s Server (%s)" % (self.name, " ".join(command_line)))

        wait_flag = self.get_wait_flag()
        if isfile(wait_flag):
            remove(wait_flag)
        self.server = Popen(command_line, stdout=PIPE, stderr=STDOUT, stdin=PIPE, creationflags=CREATION_FLAGS)
        run_logger(self.server, self.name)
        if (not self.wait_until_ready()):
            self.stop()

    def is_running(self):
        return self.server and self.server.poll() == None

    def wait_until_ready(self):
        start = time()
        for _ in xrange(self.num_tries_for_ready):
            if self.is_ready():
                return True
            else:
                sleep(0.5)
        timeout = time() - start
        msg = "%s failed to start after %s seconds" % (self.name, timeout)
        log("Sauce RC", msg)
        return False

    def is_ready(self):
        if not self.is_running():
            return False
        url = self.get_wait_flag()
        try:
            urlopen(url)
            return True
        except HTTPError, e:
            #py2.5 will take this path
            return (e.code == 403)
        except IOError:
            return False

    def stop(self):
        if not self.is_running():
            self.server = None
            return

        try:
            terminate(self.server)
            self.server.wait()
        except OSError:
            pass
        log("Sauce RC", "%s Server stopped" % self.name)
        self.server = None

class Selenium(Server):
    name = "Selenium RC"
    required_arg = []

    def construct_command_line(self, config):
        attr_list = []
        for key, value in ((k, v) for (k, v) in config.iteritems() if v):
            key = "-%s" % key.lower()
            if value is True:
                #this flag needs to be before others
                if key == "-proxyinjectionmode":
                    attr_list.insert(0, key)
                else:
                    attr_list.append(key)
            elif isinstance(value, list):
                attr_list.append(key)
                attr_list.extend([str(arg) for arg in value])
            else:
                attr_list.extend([key, str(value)])
        return [JAVA, "-jar", SELENIUM_JAR] + attr_list

    def _command_line(self, additional_params=None):
        config = load_settings("selenium")
        if additional_params: config.update(additional_params)
        return self.construct_command_line(config)

    def get_wait_flag(self):
        config = load_settings("selenium")
        return "http://127.0.0.1:%(port)s" % config


class Proxy(Server):
    name = "Sauce OnDemand"
    required_arg = ["username", "access-key"]

    def construct_command_line(self, config):
        port = str(config.pop("port", 4444))
        config.pop("force", 0)
        config["browser"] = config.get("browser", "firefox").lower()
        for key, value in config.items():
            if value == "":
                del config[key]
            if value == "Any":
                config[key] = ""
        child_opts = ["-p", port]
        debug = config.pop("debug", False)
        if debug:
            child_opts.append("-debug")
        command = [PROXY, ] + child_opts + [json.dumps(config), ]
        if not is_frozen():
            command.insert(0, executable)
        return command

    def _command_line(self, additional_params=None):
        config = load_settings("ondemand")
        if additional_params: config.update(additional_params)
        return self.construct_command_line(config)

    def get_wait_flag(self):
        config = load_settings("ondemand")
        return "http://127.0.0.1:%(port)s/ping" % config

class Tunnel(Server):
    name = "Sauce Tunnel"
    num_tries_for_ready = 300
    required_arg = ["api-key", "user", "host", "domain"]

    def construct_command_line(self, config):
        attr_list = []
        for key, value in ((k, v) for (k, v) in config.iteritems() if v):
            key = "--%s" % key.lower()
            if value is True:
                attr_list.append(key)
            elif isinstance(value, list):
                for each in value:
                    attr_list.extend([key, str(each)])
            else:
                attr_list.extend([key, str(value)])
        return [TUNNEL, ] + attr_list

    def _command_line(self, additional_params=None):
        config = load_settings("tunnel")
        auth_config = load_settings("ondemand")
        config.update((("user", auth_config["username"]),
                       ("api-key", auth_config["access-key"])))
        config["logfile"] = devnull
        config["readyfile"] = TUNNEL_FLAG
        if additional_params: config.update(additional_params)
        return self.construct_command_line(config)

    def get_wait_flag(self):
        return TUNNEL_FLAG

    def is_ready(self):
        if self.is_running() and isfile(TUNNEL_FLAG):
            return True
        else:
            return False

selenium = Selenium()
proxy = Proxy()
tunnel = Tunnel()
#TODO: fix this and make it load from prefs
current_mode = selenium

def convert_value(value):
    onoff = { "true" : True, "false" : False }
    if value in onoff:
        return onoff[value]
    return value

def save_user_config():
    if not isfile(USER_CONFIG):
        return
    copy(USER_CONFIG, USER_CONFIG + strftime(".%Y-%m-%d-%H%M%S"))

# "6.0.3790.1830." > "6."
def version_ui_name(browser, version):
    fields = version.split(".")
    n = 2 if browser.startswith("firefox") else 1 # Use minor version only in FF
    return ".".join(fields[:n]) + "."

def ui_browsers():
    with open(USER_BROWSERS_FILE) as fo:
        data = json.load(fo)

    by_os = {}
    for os, browsers in data.iteritems():
        ui_browsers = {}
        for browser, versions in browsers.iteritems():
            ui_versions = [version_ui_name(browser, v) for v in versions]
            ui_versions += ["Any"]
            ui_browsers[browser] = ui_versions
        by_os[os] = ui_browsers

    return by_os

def jsonify(func):
    def wrapper(*args, **kw):
        value = func(*args, **kw)
        cherrypy.response.headers["Content-Type"] = "application/json"
        return json.dumps(value)

    return wrapper

# FIXME: Replace all these "OK" with valid JSON
class WebServer:
    @expose
    def default(self, **query):
        return open("index.html").read()

    @expose
    def start(self, **query):
        current_mode.start()
        return "OK"

    @expose
    def stop(self, **query):
        current_mode.stop()
        return "OK"

    @expose
    def tunnel_start(self, **query):
        tunnel.start()
        return "OK"

    @expose
    def tunnel_stop(self, **query):
        tunnel.stop()
        return "OK"

    @expose
    def restart(self, **query):
        current_mode.stop()
        current_mode.start()
        return "OK"

    @expose
    def tunnel_restart(self, **query):
        tunnel.stop()
        tunnel.start()
        return "OK"

    @expose
    def switch(self, **query):
        global current_mode

        # TODO: why current_mode can't be found if it's not in self?
        selection = query["mode"]
        if selection == proxy.name:
            current_mode.stop()
            current_mode = proxy
            current_mode.start()
            if not check_ondemand_settings():
                return "to run tests on OnDemand mode,\
                        please set the Preferences properly"
            return "tests will be run in Sauce OnDemand"
        elif selection == selenium.name:
            current_mode.stop()
            current_mode = selenium
            current_mode.start()
            return "tests will be run locally"
        else:
            return "Inexistent mode, nothing changed"

    @expose
    def restore(self, **query):
        try:
            save_user_config()
            copy(DEFAULT_CFG, USER_CONFIG)
        except Exception, error:
            return error[1]
        return "OK"

    @expose
    @jsonify
    def log(self, **query):
        last_time = float(query.get("last", 0))
        lines, last = logview.get_lines(last_time)
        return {
            "last" : last,
            "log" : [escape(line) for line in lines],
        }

    @expose
    def saucerc_log(self, **query):
        cherrypy.response.headers["Content-Type"] = "text/plain"
        with open(LOG_FILE) as log:
            return log.read()

    @expose
    @jsonify
    def status(self, **query):
        if current_mode.htmlsuite_running and not current_mode.is_running():
            current_mode.htmlsuite_running = False
        return {"current_mode" : current_mode.name,
                "running" : current_mode.is_running(),
                "ready" : current_mode.is_ready(),
                "tunnel_running" : tunnel.is_running(),
                "tunnel_ready" : tunnel.is_ready(),
                "htmlsuite_running" : current_mode.htmlsuite_running,
                "new_version" : NEW_VERSION,
                "current_version" : {"version": version.version,
                                     "build": version.build,
                                     "selenium_version": version.selenium_version},
                "ondemand_reachable" : ONDEMAND_REACHABLE,
                }

    @expose
    @jsonify
    def preferences(self, **query):
        return load_config()

    @expose
    @jsonify
    def save(self, **query):
        config = load_config()
        false_bools = [option for option, old_value in config.items()
                       if option not in query and old_value == True]
        for option in false_bools:
            config[option] = False
        for key, value in query.items():
            if key.endswith("[]"): # list params have [] appeneded
                if isinstance(value, list):
                    query[key[:-2]] = query.pop(key)
                else:
                    query[key[:-2]] = [query.pop(key), ]
            elif isinstance(value, str):
                value = value.strip()
                if value == "":
                    continue
                query[key] = convert_value(value)
        config.update(query)
        try:
            save_config(config)
            return "OK"
        except IOError:
            raise cherrypy.HTTPError(httplib.INTERNAL_SERVER_ERROR)

    @expose
    def quit(self, **query):
        self.stop(**query)
        raise SystemExit

    @expose
    @jsonify
    def browsers(self, **query):
        return ui_browsers()

    @expose
    def htmlsuite(self, **query):
        global current_mode
        additional_params = {"htmlsuite": [query["htmlsuiteBrowser"],
                                           query["startURL"],
                                           query["suiteFile"],
                                           query["resultFile"]]
                            }
        current_mode.stop()
        current_mode = selenium
        current_mode.htmlsuite_running = True
        current_mode.start(additional_params)
        return "OK"

    @expose
    @jsonify
    def check_file(self, **query):
        return isfile(query.values()[0])

    @expose
    @jsonify
    def check_dir(self, **query):
        return isdir(query.values()[0])

def root_dir():
    return APPDIR if is_frozen() else join(APPDIR, "controller")

def cleanup():
    log("Sauce RC", "Shutting down Sauce RC")
    selenium.stop()
    proxy.stop()

def dump_config(fo=stdout):
    config = {
        "id-file" : ID_FILE,
        "rc-dir" : RCDIR,
        "user-config" : USER_CONFIG,
        "default-config" : DEFAULT_CFG,
        "java" : JAVA,
        "selenium-jar" : SELENIUM_JAR,
        "log-file" : LOG_FILE,
        "appdir" : APPDIR,
        "frozen" : is_frozen(),
        "server-port" : SERVER_PORT,
        "proxy" : PROXY,
    }
    json.dump(config, fo, indent=4)

def main(argv=None):
    if not argv:
        argv = sys.argv

    from optparse import OptionParser
    parser = OptionParser("%prog [options]")
    parser.add_option("--debug", "-d", help="spam with debug messages",
                      action="store_true", default=False)
    parser.add_option("-b", "--browser", help="start web browser",
                      dest="browser", default=0, action="store_true")
    parser.add_option("--config", help="dump JSON of configuration and exit",
                      dest="config", action="store_true", default=0)

    opts, args = parser.parse_args(argv[1:])
    if args:
        parser.error("wrong number of arguments") # Will exit

    if opts.config:
        dump_config()
        raise SystemExit

    ensure_user_config()
    ensure_user_config(USER_BROWSERS_FILE, BROWSERS_FILE)
    root = root_dir()
    chdir(root)

    start_logging()

    log("Sauce RC", "Sauce RC version %s started" % VERSION)

    daemon_thread(current_mode.start)
    daemon_thread(version_thread)
    daemon_thread(check_ondemand)
    daemon_thread(get_browsers)

    atexit.register(cleanup)

    config = {
        "/images" : {
            "tools.staticdir.on" : 1,
            "tools.staticdir.dir" : join(root, "images"),
        },
        "/css" : {
            "tools.staticdir.on" : 1,
            "tools.staticdir.dir" : join(root, "css"),
        },
        "/js" : {
            "tools.staticdir.on" : 1,
            "tools.staticdir.dir" : join(root, "js"),
        },
        "/static" : {
            "tools.staticdir.on" : 1,
            "tools.staticdir.dir" : join(root, "static"),
        },

    }


    if opts.browser:
        daemon_thread(open_browser_when_ready)

    cherrypy.config.update({"server.socket_host" : "0.0.0.0",
                            "server.socket_port" : SERVER_PORT,
                            "checker.check_skipped_app_config" : False,
                            "log.screen" : False,
                           })
    cherrypy.engine.reexec_retry = 20
    quickstart(WebServer(), config=config)

if __name__ == "__main__":
    main()
