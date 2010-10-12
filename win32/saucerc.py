#!/usr/bin/env python

def _setpath():
    from os.path import dirname, join, abspath
    import sys

    if not hasattr(sys, "frozen"): # not py2exe
        server_dir = abspath(join(dirname(__file__), "..", "controller"))
        sys.path.append(server_dir)
    else:
        sys.path.append("controller")
_setpath()

from common import daemon_thread, is_frozen
from env import RCDIR, SERVER_PORT, CONTROLLER, GUI_DIR

from os.path import isfile, join, isdir
from sys import executable
from tempfile import gettempdir
from subprocess import Popen, STDOUT, PIPE
from sys import platform
from time import time, sleep, ctime
from urllib import urlopen
import webbrowser
import socket
import atexit
from os import getpid, remove, mkdir
import json

import wx

CONTROLLER_LOG = join(gettempdir(), "saucerc-controller.log")
CONTROLLER_STARTUP_TIME = 30
BASE_URL = "http://localhost:%d" % SERVER_PORT
ERROR_LOG = join(GUI_DIR, "errors.log")

SAUCERC_PID = join(RCDIR, "saucerc.pid")

def log_error(message):
    with open(ERROR_LOG, "at") as fo:
        fo.write("[%s] %s\n" % (ctime(), message))

def load_icon(name):
    iconfile = join(GUI_DIR, name)
    if not isfile(iconfile):
        raise IOError

    return wx.Icon(iconfile, wx.BITMAP_TYPE_ICO)

def show_error(message):
    dlg = wx.MessageDialog(None, message, "Sauce RC Error",
            wx.OK|wx.ICON_ERROR)
    dlg.ShowModal()

def run_controller():
    command = [] if is_frozen() else [executable]
    command.append(CONTROLLER)
    fo = open(CONTROLLER_LOG, "at")
    try:
        controller = Popen(command, stdout=fo, stderr=STDOUT, stdin=PIPE)
    except OSError:
        return

    start = time()
    while time() - start < CONTROLLER_STARTUP_TIME:
        try:
            urlopen(BASE_URL)
            return controller
        except IOError:
            sleep(0.1)

def _call_controller(method):
    try:
        return urlopen("%s/%s" % (BASE_URL, method)).read()
    except (IOError, socket.error), e:
        # FIXME: Get a real web server
        log_error("Error calling '%s' - %s" % (method, e))

def call_controller(method):
    daemon_thread(_call_controller, method)

_VERSION_MESSAGE = '''
New version of Sauce RC is available:
    Version: %(version)s
    Build:   %(build)s

Download it now?
'''
def show_new_version(info):
    dlg = wx.MessageDialog(None, _VERSION_MESSAGE % info, "New Version",
                           wx.YES_NO)
    if dlg.ShowModal() == wx.ID_YES:
        webbrowser.open(info.get("download_url", "http://saucelabs.com"))

class SauceRCTrayBase(wx.TaskBarIcon):
    TBMENU_START = wx.NewId()
    TBMENU_STOP = wx.NewId()
    TBMENU_OPEN = wx.NewId()
    TBMENU_CLOSE = wx.NewId()

    def __init__(self):
        wx.TaskBarIcon.__init__(self)

        self.idle_icon = load_icon("idle.ico")
        self.running_icon = load_icon("running.ico")
        self.is_running = 0
        self.mode = "Selenium RC"
        self.new_version = None

        def handle_menu(id, handler):
            self.Bind(wx.EVT_MENU, handler, id=id)
        handle_menu(self.TBMENU_START, lambda e: call_controller("start"))
        handle_menu(self.TBMENU_STOP, lambda e: call_controller("stop"))
        handle_menu(self.TBMENU_OPEN, lambda e: webbrowser.open(BASE_URL))
        handle_menu(self.TBMENU_CLOSE, self.OnClose)

        self.Bind(wx.EVT_CLOSE, self.OnClose)
        self.Bind(wx.EVT_TASKBAR_LEFT_DOWN, lambda e: webbrowser.open(BASE_URL))
        self.Bind(wx.EVT_TASKBAR_RIGHT_DOWN, self.OnCreateMenu)

        self.update_icon()
        self.controller = run_controller()
        if not self.controller:
            show_error("Fatal error - can't run backend.\nExiting")
            self.OnClose(None)
        else:
            self.ShowBalloon(
                "Sauce RC ready",
                "Sauce RC is ready.\n"
                "You can control it from this tray icon.")

        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.OnStatus, self.timer)
        self.timer.Start(500)

    def ShowBalloon(self, title, message):
        dlg = wx.MessageDialog(None, message, title,
                wx.OK|wx.ICON_INFORMATION)
        dlg.ShowModal()

    def OnClose(self, evt):
        call_controller("quit")
        self.ShowBalloon("Quitting Sauce RC",
                         "Sauce RC is stopping.\n"
                         "It may take a few seconds.")
        if self.controller:
            for _ in range(20):
                if self.controller.poll() == None:
                    sleep(1)
                else:
                    break
            else:
                self.controller.kill()
            self.controller.wait()
            self.controller = None
        self.RemoveIcon()
        raise SystemExit

    def OnCreateMenu(self, evt):
        menu = wx.Menu()
        if self.is_running:
            menu.Append(self.TBMENU_STOP, "Stop")
        else:
            menu.Append(self.TBMENU_START, "Start")
        menu.Append(self.TBMENU_OPEN, "Open")
        menu.AppendSeparator()
        menu.Append(self.TBMENU_CLOSE, "Exit")
        self.PopupMenu(menu)
        menu.Destroy()

    def OnStatus(self, evt):
        status = _call_controller("status")
        try:
            status = json.loads(status)
        except (TypeError, ValueError):
            return

        self.is_running = status["running"]
        self.mode = status["current_mode"]
        self.update_icon()

        if self.new_version == status["new_version"]:
            return

        self.new_version = status["new_version"]
        show_new_version(self.new_version)

    def update_icon(self):
        icon = self.running_icon if self.is_running else self.idle_icon
        tooltip = "%s is not running" % self.mode
        if self.is_running:
            tooltip = tooltip.replace("not ", "")
        self.SetIcon(icon, tooltip)

if platform == "win32":
    # Shamelessly stolen from http://tinyurl.com/yf45ru6, when wx 2.9 comes it
    # this will be built in

    from win32gui import NIIF_INFO, NIF_MESSAGE, NIF_INFO, \
                         Shell_NotifyIcon, NIM_MODIFY

    def getHWND():
        for window in wx.GetTopLevelWindows():
            if window.GetWindowStyle():
                continue
            return window.GetHandle()

    class SauceRCTray(SauceRCTrayBase):
        def ShowBalloon(self, title, message):
            hwnd = getHWND()

            if not hwnd:
                SauceRCTrayBase.ShowBalloon(self, title, message)
                return

            hicon = self.running_icon.GetHandle()
            lpdata = (
                    hwnd, # hWND
                    99, # ID
                    NIF_MESSAGE|NIF_INFO|NIF_INFO, # flags
                    0, # CallbackMessage
                    hicon, # Icon to display
                    "", # Tooltip
                    message, # Message
                    0, # Timeout in msec
                    title, # Info title
                    NIIF_INFO # InfoFlags
            )
            Shell_NotifyIcon(NIM_MODIFY, lpdata)
            # For some reason this is needed to re-enable menus
            self.update_icon()

else: # Linux and unknown
    SauceRCTray = SauceRCTrayBase

def write_pid_file():
    with open(SAUCERC_PID, "w") as fo:
        print >> fo, getpid()

def delete_pid_file():
    if isfile(SAUCERC_PID):
        try:
            remove(SAUCERC_PID)
        except OSError, e:
            log_error("Can't delete pid file - %s" % e)

def main():
    app = wx.PySimpleApp()

    checker = wx.SingleInstanceChecker(".saucerc-lock-%s" % wx.GetUserId())
    if checker.IsAnotherRunning():
        dlg = wx.MessageDialog(None,
                               "Sauce RC is already running.\n"
                               "Have a look at the system tray.",
                               "Already Running",
                               wx.ICON_ERROR)
        dlg.ShowModal()
        raise SystemExit(1)

    if not isdir(RCDIR):
        mkdir(RCDIR)

    # The installer is using this PID file
    write_pid_file()
    atexit.register(delete_pid_file)

    tray = SauceRCTray()
    app.MainLoop()

if __name__ == "__main__":
    main()
