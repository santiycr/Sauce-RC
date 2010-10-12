from env import LOG_FILE
from common import daemon_thread
from logview import add_line

from logging import getLogger, Formatter, DEBUG, Handler
from logging.handlers import RotatingFileHandler
from Queue import Queue
from time import time, strftime, localtime

LOGGER_NAMES = ("Selenium RC", "Sauce RC", "Sauce OnDemand", "Sauce Tunnel")
NAME_LENGTH = max(len(n) for n in LOGGER_NAMES)
MESSAGE_QUEUE = Queue()

def msec(t):
    return ("%03d" % int((t - int(t))*1000))

class TailHandler(Handler):
    def emit(self, record):
        add_line(record.getMessage())

def create_loggers():
    MB = 1024 * 1024
    handler = RotatingFileHandler(LOG_FILE, "a", 2 * MB, 1)
    tail_handler = TailHandler()
    handler.setFormatter(Formatter("%(message)s"))

    def logger(name):
        logger = getLogger(name)
        logger.setLevel(DEBUG)
        logger.addHandler(handler)
        logger.addHandler(tail_handler)
        return logger

    return dict((name, logger(name)) for name in LOGGER_NAMES)

def add_timestamp(t, message):
    timestamp = strftime("%H:%M:%S", localtime(t))

    return "%s.%s INFO - %s" % (timestamp, msec(t), message)

def logger_thread():
    has_timestamp = set(["Selenium RC", "Sauce OnDemand"])
    loggers = create_loggers()

    while 1:
        t, name, message = MESSAGE_QUEUE.get()
        if name not in has_timestamp:
            message = add_timestamp(t, message)
        message = "[%-*s] %s" % (NAME_LENGTH, name, message)
        loggers[name].info(message)

def start_logging():
    daemon_thread(logger_thread)

def log(name, message):
    MESSAGE_QUEUE.put((time(), name, message))

def run_logger(server_process, name):
    def logfunc():
        while True:
            try:
                line = server_process.stdout.readline()
            except AttributeError:
                break
            exitcode = server_process.poll()
            if (not line) and (exitcode is not None):
                break
            if line:
                line = line.decode("utf8", "replace")
                log(name, line.rstrip())
    daemon_thread(logfunc)
