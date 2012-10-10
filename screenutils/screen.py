# -*- coding:utf-8 -*-
#
# This program is free software. It comes without any warranty, to
# the extent permitted by applicable law. You can redistribute it
# and/or modify it under the terms of the GNU Public License 2 or upper.
# Please ask if you wish a more permissive license.
import subprocess
from os.path import isfile, getsize
from time import sleep

from errors import ScreenNotFoundError


def _check_output(*popenargs, **kwargs):
    """ Does the same thing as subprocess.check_output but ignores the return code.
    
    This is done becaues screen does not always return exit code 0
    when running normal commands.
    'screen -ls' returns exit code 1 and therefore the normal check_output fails.
    
    """
    process = subprocess.Popen(stdout=subprocess.PIPE, *popenargs, **kwargs)
    output, unused_err = process.communicate()
    return output

def tailf(file_):
    """Each value is content added to the log file since last value return"""
    last_size = getsize(file_)
    while True:
        cur_size = getsize(file_)
        if ( cur_size != last_size ):
            f = open(file_, 'r')
            f.seek(last_size if cur_size > last_size else 0)
            text = f.read()
            f.close()
            last_size = cur_size
            yield text
        else:
            yield ""

def list_session_names():
    """List all the exists sessions
    """
    output = _check_output("screen -ls | grep -P '\t'", shell=True).split('\n')
    return [
                ".".join(l.split(".")[1:]).split("\t")[0]
                for l in output
                if ".".join(l.split(".")[1:]).split("\t")[0]
            ]

def list_screens():
    """List all the existing screens and build a Screen instance for each
    """
    return map(lambda x: Screen(x), list_session_names())


class Screen(object):
    """Represents a gnu-screen object::

        >>> s=Screen("screenName", initialize=True)
        >>> s.name
        'screenName'
        >>> s.exists
        True
        >>> s.state
        >>> s.send_commands("man -k keyboard")
        >>> s.kill()
        >>> s.exists
        False
    """

    def __init__(self, name, initialize=False):
        self.name = name
        self._id = None
        self._status = None
        self.logs=None
        if initialize:
            self.initialize()

    @property
    def id(self):
        """return the identifier of the screen as string"""
        if not self._id:
            self._set_screen_infos()
        return self._id

    @property
    def status(self):
        """return the status of the screen as string"""
        self._set_screen_infos()
        return self._status

    @property
    def exists(self):
        """Tell if the screen session exists or not."""
        # Parse the screen -ls call, to find if the screen exists or not.
        # The screen -ls | grep name returns something like that:
        #  "	28062.G.Terminal	(Detached)"
        sessions = list_session_names()
        return self.name in sessions

    def enable_logs(self):
        self._screen_commands("logfile " + self.name, "log on")
        subprocess.call(["touch", self.name])
        self.logs=tailf(self.name)
        next(self.logs)

    def disable_logs(self):
        self._screen_commands("log off")
        self.logs=None

    def initialize(self, force=False):
        """initialize a screen, if does not exists yet"""
        if force or not self.exists:
            self._id=None
            subprocess.call(["screen", "-Udm", self.name])

    def interrupt(self):
        """Insert CTRL+C in the screen session"""
        self._screen_commands("eval \"stuff \\003\"")

    def kill(self):
        """Kill the screen applications then close the screen"""
        self._screen_commands('quit')

    def detach(self):
        """detach the screen"""
        self._check_exists()
        subprocess.call(["screen", "-d", self.name])

    def send_commands(self, *commands):
        """send commands to the active gnu-screen"""
        self._check_exists()
        for command in commands:
            self._screen_commands( 'stuff "' + command + '"\r')#, 'eval "stuff \r"' )

    def add_user_access(self, unix_user_name):
        """allow to share your session with an other unix user"""
        self._screen_commands('multiuser on', 'acladd ' + unix_user_name)

    def _screen_commands(self, *commands):
        """allow to insert generic screen specific commands
        a glossary of the existing screen command in `man screen`"""
        self._check_exists()
        for command in commands:
            cmd = ["screen", "-r", self.name, "-p", "0", "-X", command]
            subprocess.call(" ".join(cmd), shell=True)
            sleep(0.02)

    def _check_exists(self, message="Error code: 404"):
        """check whereas the screen exist. if not, raise an exception"""
        if not self.exists:
            raise ScreenNotFoundError(message)

    def _set_screen_infos(self):
        """set the screen information related parameters"""
        if self.exists:
            infos = _check_output("screen -ls | grep %s" % self.name, shell=True).split('\t')[1:]
            self._id = infos[0].split('.')[0]
            if len(infos)==3:
                self._date = infos[1][1:-1]
                self._status = infos[2][1:-2]
            else:
                self._status = infos[1][1:-2]

    def __repr__(self):
        return "<%s '%s'>" % (self.__class__.__name__, self.name)
