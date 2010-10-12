#!/usr/bin/env python

'''This script is called by the uninstaller before starting'''


from sys import platform
from glob import glob
from os import remove
from os.path import basename, join
from urllib import urlopen
from time import sleep
import socket

from controller import env
from controller.env import SERVER_PORT

import wx

if platform == "win32":
    import win32api
    import win32con
    import win32process
    import pywintypes

    def kill(pid):
        h = win32api.OpenProcess(win32con.PROCESS_TERMINATE, 0, pid)
        try:
            win32process.TerminateProcess(h, 0)
        finally:
            win32api.CloseHandle(h)

    def get_pid_exe(pid):
        h = None
        try:
            h = win32api.OpenProcess(win32con.PROCESS_ALL_ACCESS, False, pid)
            filepath = win32process.GetModuleFileNameEx(h, 0)
            return basename(filepath)
        except pywintypes.error:
            return ""
        finally:
            if h:
                win32api.CloseHandle(h)

    def iter_processes():
        pids = win32process.EnumProcesses()
        for pid in pids:
            name = get_pid_exe(pid)
            if not name:
                continue
            yield pid, name
else:
    from os import kill as _kill
    from subprocess import Popen, PIPE
    from signal import SIGTERM

    def iter_processes():
        pipe = Popen(["ps", "-Af"], stdout=PIPE).stdout
        pipe.readline() # Skip header
        for line in pipe:
            fields = line.split(None, 7)
            pid = int(fields[1])
            command = fields[-1]
            name = basename(command.split()[0])
            yield pid, name

    def kill(pid):
        _kill(pid, SIGTERM)


SAUCE_PROCESSES = set([
    "saucerc.exe",
    "sauceserver.exe",
    "sauceproxy.exe",
])

def is_sauce(name):
    return name in SAUCE_PROCESSES

def sauce_processes():
    return ((pid, name) for pid, name in iter_processes() if is_sauce(name))

def show_error(message):
    dlg = wx.MessageDialog(None, message, "Error", wx.OK | wx.ICON_ERROR)
    dlg.ShowModal()

def quit_saucerc():
    BASE_URL = "http://localhost:%d" % SERVER_PORT
    for i in range(10):
        try:
            return urlopen("%s/quit" % BASE_URL).read()
        except (IOError, socket.error):
            return
        sleep(1)

def clean_processes():
    processes = filter(lambda args: is_sauce(args[1]), iter_processes())
    if processes:
        names = ", ".join((p[1] for p in processes))
        message = "Sauce RC seems to be running (%s)\nForce quit before uninstalling? (Yes recommended)" % names
        dlg = wx.MessageDialog(None, message, "Found Stray Processes", wx.YES_NO)
        if dlg.ShowModal() != wx.ID_YES:
            return

        for pid, name in processes:
            try:
                kill(pid)
            except OSError:
                show_error("can't kill %s (pid=%s)" % (name, pid))
            except pywintypes.error:
                show_error("Problems killing %s (pid=%s).\nIt may still be running" % (name,
                                                                                       pid))

def clean_pid_files():
    for path in glob(join(env.RCDIR, "*.pid")):
        try:
            remove(path)
        except OSError:
            show_error("Can't delete %s" % path)

def main():
    app = wx.PySimpleApp()
    steps = (
        (quit_saucerc, "Shutting Down Sauce RC"),
        (clean_processes, "Cleaning Processes"),
        (clean_pid_files, "Cleaning PID Files")
    )
    max_caption = max((len(step[1]) for step in steps))
    dlg = wx.ProgressDialog("Pre Uninstall Cleanup", " " * max_caption,
                            maximum=len(steps))

    for i, (func, caption) in enumerate(steps):
        dlg.Update(i + 1, caption)
        func()
    dlg.Destroy()

if __name__ == "__main__":
    main()
