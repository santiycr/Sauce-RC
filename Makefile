# For building you'll need
#
# General:
# * Python 2.6 (http://www.python.org)
# * docutils (http://docutils.sourceforge.net/)
#
# Windows:
# * wxPython (http://wxpython.org)
# * pywin32 (http://sourceforge.net/projects/pywin32/)
# * py2exe (http://www.py2exe.org/)
#   - if you're having problems with msvcp90.dll when building: 
#     http://www.py2exe.org/index.cgi/Tutorial#Step52
# * InnoSetup (http://www.jrsoftware.org/isinfo.php)
# * A Unix like environment with make, rm, cp and curl
# 	- I'm using http://code.google.com/p/msysgit/
#   - For this Makefile to work, you'll need Python and Inno Setup in your path
#
# Mac:
# * Platypus (http://www.sveinbjorn.org/platypus)

ISCC = $(shell python innoexe.py)

all: 
	@echo Please specify "windows" or "mac"

mac: prebuild macdist cleanup

macdist: docs platypus mac-dmg

platypus:
	rm -fr dist;mkdir dist
	/usr/local/bin/platypus -P mac/SauceRC.platypus \
		dist/Sauce\ RC.app

mac-dmg:
	sh ./build-mac-dmg

windows: prebuild iscc cleanup

iscc: dist vcredist_x86.exe
	$(ISCC) setup.iss
	rm -fr dist

dist: py2exe distfiles

py2exe:
	rm -fr dist
	python setup_windows.py py2exe

distfiles: docs
	cp win32/*.ico dist
	cp controller/selenium-server.jar dist
	cp controller/index.html dist
	cp controller/default-config.json dist
	cp -r controller/css dist
	cp -r controller/js dist
	cp -r controller/images dist
	cp -r controller/static dist
	cp controller/browsers.json dist

docs:
	python rst2html.py --stylesheet docs/voidspace.css \
	    --embed-stylesheet \
	    docs/index.rst docs/index.html
	cp -r docs controller/static

cleanup:
	rm docs/index.html
	rm -rf controller/static/docs

vcredist_x86.exe:
	test -s $@ || curl -L -o $@ http://download.microsoft.com/download/1/1/1/1116b75a-9ec3-481a-a3c8-1777b5381140/vcredist_x86.exe

test: clean
	./runtests --with-xunit

cxfreeze:
	sh ./build-cxfreeze

prebuild: clean
	sh ./prebuild

clean:
	rm -f Output/*.exe
	rm -f Output/*.dmg
	rm -f dist/*.dmg
	rm -rf dist/*.app
	python clean.py

.PHONY: all iscc py2exe dist docs test prebuild clean
