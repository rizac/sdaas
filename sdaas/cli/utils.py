"""
(C)ommand (L)ine (I)nterface utilities

Created on 10 Sep 2020

@author: Riccardo Z. <rizac@gfz-potsdam.de>
"""
import os
import sys
from datetime import datetime
from contextlib import contextmanager
import math
import shutil
from typing import TextIO


def isatty(stream):
    """Return true if the given stream (e.g. sys.stdout, sys.stderr)
    is interactive
    """
    # isatty is not always implemented, #6223 (<- of which project???)
    try:
        return stream.isatty()
    except AttributeError:
        return False


class ansi_colors_escape_codes:
    """Ansi colors escape codes. For info see:
    https://stackoverflow.com/a/287944
    """
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[32m'  # '\033[92m'
    WARNING = '\033[33m'  # '\033[93m'
    FAIL = '\033[31m'  # '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

    @staticmethod
    def are_supported_on_current_terminal():
        """Return True if the running system's terminal supports color,
        and False otherwise. Copied from:
        https://github.com/django/django/blob/master/django/core/management/color.py#L12
        """
        supported_platform = sys.platform != 'win32' or 'ANSICON' in os.environ
        return supported_platform and isatty(sys.stdout)


@contextmanager
def redirect(src=None, dst=os.devnull):
    """Prevent Python AND external C shared library to print to
    stdout/stderr in python, preventing also leaking file descriptors.
    If the first argument is None or any object not having a fileno() argument,
    this context manager is simply no-op and will yield and then return

    See https://stackoverflow.com/a/14797594

    Example

    with redirect(sys.stdout):
        print("from Python")
        os.system("echo non-Python applications are also supported")

    :param src: file-like object with a fileno() method. Usually is either
        `sys.stdout` or `sys.stderr`
    """

    # some tools (e.g., pytest) change sys.stderr. In that case, we do want
    # this function to yield and return without changing anything
    # Moreover, passing None as first argument means no redirection
    if src is not None:
        try:
            file_desc = src.fileno()
        except (AttributeError, OSError) as _:
            src = None

    if src is None:
        yield
        return

    # if you want to assert that Python and C stdio write using the same file
    # descriptor:
    # assert libc.fileno(ctypes.c_void_p.in_dll(libc, "stdout")) == file_desc == 1

    def _redirect_stderr_to(fileobject):
        sys.stderr.close()  # + implicit flush()
        # make `file_desc` point to the same file as `fileobject`.
        # First closes file_desc if necessary:
        os.dup2(fileobject.fileno(), file_desc)
        # Make Python write to file_desc
        sys.stderr = os.fdopen(file_desc, 'w')

    def _redirect_stdout_to(fileobject):
        sys.stdout.close()  # + implicit flush()
        # make `file_desc` point to the same file as `fileobject`.
        # First closes file_desc if necessary:
        os.dup2(fileobject.fileno(), file_desc)
        # Make Python write to file_desc
        sys.stdout = os.fdopen(file_desc, 'w')

    _redirect_to = _redirect_stderr_to if src is sys.stderr else _redirect_stdout_to

    with os.fdopen(os.dup(file_desc), 'w') as src_fileobject:
        with open(dst, 'w') as dst_fileobject:
            _redirect_to(dst_fileobject)
        try:
            yield  # allow code to be run with the redirected stdout/err
        finally:
            # restore stdout/err. buffering and flags such as CLOEXEC may be different:
            _redirect_to(src_fileobject)


class ProgressBar:
    """Produce progress bar with ANSI code output"""

    # Code modified from:
    # https://mike42.me/blog/2018-06-make-better-cli-progress-bars-with-unicode-block-characters

    def __init__(self, target: TextIO or None = sys.stderr,
                 show_percent=True, show_eta=True):
        self._target = target
        self._text_only = not isatty(self._target)
        self._show_percent = show_percent
        self._show_eta = show_eta
        self._start = None
        self._lpad, self._rpad = '[', ']'  # pbar paddings (left and right)

    def __enter__(self):
        if self._show_eta:
            self._start = datetime.utcnow()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self._target:
            return
        if exc_type is None:
            # Set to 100% for neatness, if no exception is thrown
            self.set_progress(1.0)
        if not self._text_only:
            # ANSI-output should be rounded off with a newline
            self._target.write('\n')
        self._target.flush()

    def set_progress(self, progress: float):
        """0 <= progress <= 1 """
        if not self._target:
            return
        # Update width in case of resize
        width, _ = shutil.get_terminal_size((80, 20))
        # on our terminal, it is visually nicer to leave the last char
        # empty as it is filled with a square semi-opaque cursor
        # let's leave the last char empty (this has no bad visual effect and
        # will assure we see all info on any terminal):
        width -= 1

        min_pbar_width = 3
        if width < min_pbar_width:
            return

        # adjust left and right padding. If there is no space, remove padding:
        lpad, rpad = self._lpad, self._rpad
        if width >= min_pbar_width + len(lpad) + len(rpad):
            width -= len(lpad) + len(rpad)
        else:
            lpad, rpad = '', ''

        # Progress bar itself
        eta_str, eta_width = '', 13  # <- length of eta string
        if self._show_eta and width >= eta_width + min_pbar_width:
            eta = (1-progress) * \
                (datetime.utcnow() - self._start) / progress
            sec = round(eta.total_seconds() + 1e-7)
            # 1e-7 because python 3 rounds down 0.5, and we want it up. See
            # https://stackoverflow.com/questions/10825926/python-3-x-rounding-behavior
            day = int(sec / (3600 * 24))
            sec -= day * (3600 * 24)
            if day >= 100:
                eta_str = f'>={str(day)}d'.rjust(eta_width)
            else:
                hrs = int(sec / 3600)
                sec -= hrs * 3600
                mnt = int(sec / 60)
                sec -= mnt * 60
                eta_str = f' {day:>2}d {hrs:02}:{mnt:02}:{sec:02}'
            width -= eta_width

        percent_str, percent_width = '', 4  # <- length of perc. string
        if self._show_percent and width >= percent_width + min_pbar_width:
            percent_str = "{:3d}%".format(int(0.5 + progress * 100))
            width -= percent_width

        pbar_str = ProgressBar.progress_bar_str(progress, width)

        # Write output
        pbar_str = f'{lpad}{pbar_str}{rpad}{percent_str}{eta_str}'
        if self._text_only:
            self._target.write(pbar_str + '\n')
        else:
            self._target.write('\033[G' + pbar_str)
        self._target.flush()

    @staticmethod
    def progress_bar_str(progress: float, width: int):
        # 0 <= progress <= 1
        progress = min(1, max(0, progress))
        whole_width = math.floor(progress * width)
        remainder_width = (progress * width) % 1
        part_width = math.floor(remainder_width * 8)
        part_char = [" ", "▏", "▎", "▍", "▌", "▋", "▊", "▉"][part_width]
        if (width - whole_width - 1) < 0:
            part_char = ""
        line = "█" * whole_width + part_char + " " * (width - whole_width - 1)
        return line
