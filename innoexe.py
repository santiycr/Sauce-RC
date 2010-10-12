#!/usr/bin/env python


def main():
    from _winreg import OpenKey, QueryValue, HKEY_LOCAL_MACHINE
    import shlex
    from os.path import join, dirname

    path = r"SOFTWARE\Classes\InnoSetupScriptFile\shell\Compile\command"
    key = OpenKey(HKEY_LOCAL_MACHINE, path)
    command = QueryValue(key, "")
    compiler = shlex.split(command)[0]
    print join(dirname(compiler), "ISCC.exe")

if __name__ == "__main__":
    from sys import platform
    if platform != "win32":
        print ""
        raise SystemExit

    try:
        main()
    except (WindowsError, ImportError):
        print "ISCC.exe" # FIXME: Find the right registry path

