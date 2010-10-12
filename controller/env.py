from common import is_frozen

from os.path import join, dirname, abspath
from sys import platform, executable
from os import environ

if is_frozen():
    APPDIR = abspath(dirname(executable))
    CONTROLLER_DIR = GUI_DIR = APPDIR
    CONTROLLER = join(CONTROLLER_DIR, "sauceserver")
    PROXY = join(CONTROLLER_DIR, "sauceproxy")
    TUNNEL = join(CONTROLLER_DIR, "sauce_tunnel")
    if platform == "win32":
        CONTROLLER += ".exe"
        PROXY += ".exe"
        TUNNEL += ".exe"
else:
    APPDIR = abspath(join(dirname(__file__), ".."))
    CONTROLLER_DIR = join(APPDIR, "controller")
    CONTROLLER = join(CONTROLLER_DIR, "server.py")
    PROXY = join(CONTROLLER_DIR, "proxy.py")
    TUNNEL = join(CONTROLLER_DIR, "sauce_tunnel")
    # FIXME: OS X?
    GUI_DIR = join(APPDIR, "win32")

if platform == "win32":
    import win32process
    CREATION_FLAGS = win32process.CREATE_NO_WINDOW
else:
    CREATION_FLAGS = 0

JAVA = "java"

SELENIUM_JAR = join(CONTROLLER_DIR, "selenium-server.jar")
DEFAULT_CFG = join(CONTROLLER_DIR, "default-config.json")

if platform == "win32":
    RCDIR = join(environ["APPDATA"], "SauceRC")
else:
    RCDIR = join(environ["HOME"], ".saucerc")
USER_CONFIG = join(RCDIR, "config.json")
TUNNEL_FLAG = join(RCDIR, "tunnel.ready")
SELENIUM_PID = join(RCDIR, "seleniumrc.pid")
LOG_FILE = join(RCDIR, "saucerc.log")
ID_FILE = join(RCDIR, "saucerc.id")
BROWSERS_FILE = join(CONTROLLER_DIR, "browsers.json")
USER_BROWSERS_FILE = join(RCDIR, "browsers.json")

SERVER_PORT = 8421

ONDEMANDHOST, ONDEMANDPORT = "ondemand.saucelabs.com", 80
