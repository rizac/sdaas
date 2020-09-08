'''
Created on 18 Jun 2020

@author: riccardo
'''
from contextlib import contextmanager
import os
import sys

import numpy as np

from sdaas.psd import psd_values


PSD_PERIODS_SEC = (5.,)  # use floats for safety (numpy cast errors?)
FEATURES = tuple(PSD_PERIODS_SEC)


def get_features_from_traces(traces, metadata, capture_stderr=False):
    '''Computes the (1-dimensional) feature space for any given ObsPy Traces,
    element-wise. The feature is the PSD in decibels at 5 seconds. The returned
    value can be used as input in `featscore` to compute the traces anomaly
    scores, also element-wise.

    :see: `featappend` to concatenate two feature arrays returned from this
        method

    :param traces: an iterable of ObsPy Traces (e.g., list of trace, or ObsPy
        Stream object). Tocompute the PSD features of a single trace, pass
        the 1-element list `[trace]`.
    :param metadata: the traces metadata (Obspy Inventory object), usually
        obtained by calling `read_inventory` on a given StationXML file
        (https://www.fdsn.org/xml/station/)
    :capture_stderr: boolean (default False) captures all standard error
        messages issued by this package AND external libraries. Useful
        if executing from terminal to avoid useless huge amounts of potential
        printouts. The function that most likely causes these kind of issues
        is obspy inventory `read` function. From obspy > 1.1.1, the function
        will have a flag (boolean argument) to achieve that (when, it depends
        on when the version with our merged PR will be released)

    :return: a [M, 1] numpy array of floats representing the feature of the
        given traces, element-wise
    '''
    values = np.full((len(traces), len(FEATURES)), np.nan, dtype=float)
    # `redirect` below will capture and ignore printouts to stderr issued from
    # external (non Python) libraries: what happens is that `psd_values` below
    # calls `obspy.core.inventory.response.get_evalresp_response(...)`
    # which in turns calls external C libraries which might print warnings
    # to stderr. Note that ObsPy has a parameter to silence these printouts
    # (hide_sensitivu=ity_mismatch_warning) but it's not currently accessible
    # in version 1.1.1. It will be in the future (our PR was successfully merged)
    with redirect(sys.stderr if capture_stderr else None):
        for i, trace in enumerate(traces):
            try:
                values[i, :] = psd_values(FEATURES, trace, metadata)
            except ValueError:
                pass
    return values


def featappend(features1, features2):
    '''Calls numpy.append(features1, features2) and works also if one
    inputs Nones or empty arrays

    :param features1: a Nx1 array of features, e.g. the output of
        `get_features_from_traces`. None or the empty arrays (including empty
        lists / tuples) are also valid
    :param features2: a Nx1 array of features, e.g. the output of
        `get_features_from_traces`. None or the empty arrays (including empty
        lists / tuples) are also valid

    :return features1 + features2 in a single M x 1 array
    '''
    flen = len(FEATURES)

    if features1 is None or not len(features1):
        features1 = np.full(shape=(0, flen), fill_value=np.nan)
    if features2 is None or not len(features2):
        features2 = np.full(shape=(0, flen), fill_value=np.nan)

    return np.append(features1, features2, axis=0)


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
