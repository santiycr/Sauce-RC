from distutils.core import setup
import py2exe


def script(script, name):
    return {
        "script" : script,
        "dest_base" : name,
        "icon_resources" : [(1, "win32/running.ico")],
    }

SCRIPTS = (
    ("win32/saucerc.py", "saucerc"),
    ("controller/server.py", "sauceserver"),
    ("uninstall_cleanup.py", "uninstall_cleanup"),
)

options = {
           'dll_excludes': [ "mswsock.dll", "powrprof.dll" ],
          }

import sys; sys.path.extend(["controller", "controller/lib"])
setup(
    windows = [ script(path, name) for path, name in SCRIPTS ],
    console = [ script("controller/proxy.py", "sauceproxy") ],
    options = {"py2exe": options}
)
