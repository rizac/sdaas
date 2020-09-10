'''
(C)ommand (L)ine (I)nterface utilities

Created on 10 Sep 2020

@author: riccardo
'''
import os
import sys
from contextlib import contextmanager


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

        # isatty is not always implemented, #6223.
        is_a_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
        return supported_platform and is_a_tty


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
