#!/usr/bin/env python
'''Proxy from localhost:4444 to saucelabs'''

from env import ONDEMANDHOST, ONDEMANDPORT, CONTROLLER_DIR

# CherryPy must be in sys.path
import sys, os; sys.path.append(os.path.join(CONTROLLER_DIR, "lib"))
import cherrypy
from cherrypy import expose, HTTPError


import httplib
from httplib import HTTPConnection
from urllib import urlencode
try:
    import json
except ImportError:
    import simplejson as json
import re
import logging

from cherrypy import expose, HTTPError

def _setup_logging():
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)

    formatter = logging.Formatter("%(asctime)s.%(msecs)03d %(levelname)s - %(message)s",
                                  "%H:%M:%S")
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    return logger

def construct_headers(data, headers):
    h = {}
    for key, value in headers.items():
        h[key.title()] = value

    h["Content-Length"] = len(data)

    return h

is_driver_path = re.compile("^/selenium-server/driver/?$").match

def new_browser_command(command, cmd_line_settings):
    try:
        settings = json.loads(command)
    except ValueError:
        logger.debug("Browser recieved from client is not JSON, replacing with settings")
        return json.dumps(cmd_line_settings)
    logger.debug("Browser recieved from client is JSON, sending directly")
    return json.dumps(settings)


class WebServer:
    def __init__(self, debug, settings):
        self.settings = settings
        self.debug = debug

    @expose
    def default(self, *path, **query):
        if path == ("ping",):
            cherrypy.response.headers["Content-Type"] = "text/plain"
            return "pong"

        request = cherrypy.request
        if not is_driver_path(request.path_info):
            raise HTTPError(httplib.FORBIDDEN)

        query.setdefault("1", "")
        query.setdefault("2", "")
        query.setdefault("sessionId", "null")
        logger.info("Command request: %(cmd)s[%(1)s, %(2)s] on session %(sessionId)s" % query)

        if query.get("cmd", "") == "getNewBrowserSession":
            try:
                query["1"] = new_browser_command(query["1"], self.settings)
                logger.info("Starting new test: %s" % query["1"])
            except ValueError:
                raise HTTPError(httplib.BAD_REQUEST, "malformed JSON")

        conn = HTTPConnection(ONDEMANDHOST, ONDEMANDPORT)
        data = urlencode(query)
        headers = construct_headers(data, request.headers)
        for key, value in headers.items():
            logger.debug(" - Client - %s: %s", key, value)
        logger.debug(" - Client - %s", data)

        try:
            conn.request("POST", "/selenium-server/driver/", data, headers)
        except:
            error = "Error connecting to OnDemand, please check your internet connection"
            logger.error(error)
            return error

        response = conn.getresponse()
        data = response.read()
        headers = construct_headers(data, dict(response.getheaders()))
        if response.chunked:
            headers.pop("Transfer-Encoding", None)

        cherrypy.response.status = response.status
        headers = cherrypy.response.headers

        for header, value in headers.iteritems():
            header = header.title()
            logger.debug(" - Server - %s: %s", header, value)
            headers[header] = value
        logger.debug(" - Server - %s", data)

        if query.get("cmd", "") == "getNewBrowserSession":
            if not "OK" in data:
                logger.error(data)
                return data
            else:
                session = data[data.find(",") + 1:]
        else:
            session = query["sessionId"]
        logger.info("Got result: %s on session %s" % (data, session))
        if query.get("cmd", "") == "testComplete":
            logger.info("Test Finished, you can see the server side log and video at http://saucelabs.com/jobs/%s" % query["sessionId"])

        return data

def main(argv=None):
    if not argv:
        import sys
        argv = sys.argv

    from optparse import OptionParser
    parser = OptionParser("%prog [options] JSON_CONFIG")
    parser.add_option("--debug", "-d", help="spam with debug messages",
                      action="store_true", default=False, dest="debug")
    parser.add_option("-p", "--port", help="port to listen on", dest="port",
                      type="int", default=4444)
    opts, args = parser.parse_args(argv[1:])

    if len(args) != 1:
        parser.error("wrong number of arguments") # Will exit

    try:
        settings = json.loads(args[0])
    except ValueError, e:
        parser.error("Invalid JSON config: %s" % e) # Will exit
    port = opts.port

    global logger
    logger = _setup_logging()
    if opts.debug:
        logger.setLevel(logging.DEBUG)

    logger.info("Listening on port %d" % port)

    cherrypy.config.update({
        "server.socket_host" : "0.0.0.0",
        "server.socket_port" : port,
        "log.screen" : opts.debug,
        "checker.check_skipped_app_config" : False,
    })
    cherrypy.quickstart(WebServer(opts.debug, settings), "/", {})

if __name__ == "__main__":
    main()
