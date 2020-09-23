'''
(C)ommand (L)ine (I)nterface utilities

Created on 10 Sep 2020

@author: riccardo
'''
import os
import sys
from contextlib import contextmanager
import math
import shutil
from typing import TextIO


def isatty(stream):
    '''
    returns true if the given stream (e.g. sys.stdout, sys.stderr)
    is interactive
    '''
    # isatty is not always implemented, #6223 (<- of which project???)
    try:
        return stream.isatty()
    except AttributeError:
        return False


class ansi_colors_escape_codes:
    '''
    Ansi colors escape codes. For info see:
    https://stackoverflow.com/a/287944
    '''
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
        """
        Return True if the running system's terminal supports color,
        and False otherwise. Copied from:
        https://github.com/django/django/blob/master/django/core/management/color.py#L12
        """
        supported_platform = sys.platform != 'win32' or 'ANSICON' in os.environ
        return supported_platform and isatty(sys.stdout)


@contextmanager
def redirect(src=None, dst=os.devnull):
    '''
    This method prevents Python AND external C shared library to print to
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
    '''

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
    """
    Produce progress bar with ANSI code output.
    """
    # Code modified from:
    # https://mike42.me/blog/2018-06-make-better-cli-progress-bars-with-unicode-block-characters

    def __init__(self, target: TextIO or None = sys.stderr):
        self._target = target
        self._text_only = not isatty(self._target)
        if self._target:
            self._update_width()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            # Set to 100% for neatness, if no exception is thrown
            self.update(1.0)
        if not self._text_only:
            # ANSI-output should be rounded off with a newline
            self._target.write('\n')
        self._target.flush()

    def _update_width(self):
        self._width, _ = shutil.get_terminal_size((80, 20))

    def update(self, progress: float):
        if not self._target:
            return
        # Update width in case of resize
        self._update_width()
        # Progress bar itself
        if self._width < 12:
            # No label in excessively small terminal
            percent_str = ''
            progress_bar_str = ProgressBar.progress_bar_str(progress, self._width - 2)
#         elif self._width < 40:
#             # No padding at smaller size
#             percent_str = "{:6.2f} %".format(progress * 100)
#             progress_bar_str = ProgressBar.progress_bar_str(progress, self._width - 11) + ' '
#         else:
#             # Standard progress bar with padding and label
#             percent_str = "{:6.2f} %".format(progress * 100) + "  "
#             progress_bar_str = " " * 5 + ProgressBar.progress_bar_str(progress, self._width - 21)
        else:
            percent_str = "{:6.2f} %".format(progress * 100)
            progress_bar_str = ProgressBar.progress_bar_str(progress, self._width - 11)

        # Write output
        if self._text_only:
            self._target.write(progress_bar_str + percent_str + '\n')
            self._target.flush()
        else:
            self._target.write('\033[G' + progress_bar_str + percent_str)
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
        line = "[" + "█" * whole_width + part_char + " " * (width - whole_width - 1) + "]"
        return line
