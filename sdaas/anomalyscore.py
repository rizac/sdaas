'''
Created on 18 Jun 2020

@author: riccardo
'''
import numpy as np
from os.path import join, dirname

from joblib import load

from sdaas.psd import psd_values
from sklearn.ensemble.iforest import IsolationForest
from contextlib import contextmanager
import os
import sys


PSD_PERIODS_SEC = (5.,)  # use floats for safety (numpy cast errors?)
FEATURES = tuple(PSD_PERIODS_SEC)
DEFAULT_TRAINED_MODEL = load(join(dirname(__file__),
                                  'clf=IsolationForest&'
                                  'tr_set=uniform_train.hdf&'
                                  'feats=psd@5sec&'
                                  'behaviour=new&'
                                  'contamination=auto&'
                                  'max_samples=1024&'
                                  'n_estimators=100&'
                                  'random_state=11'
                                  '.sklmodel'))


def tracescore(traces, metadata):
    '''Computes the amplitude anomaly score in [0, 1] from the given ObsPy
    Traces element wise. The closer a scores is to 1, the more likely it
    represents an anomaly. Note however that in the practice scores are returned
    in the range [0.4, 0.8]: scores <=0.5 can be safely considered inliers
    (with no particular numerical meaning), and - for binary classification -
    scores >0.5 need to inspected to determine the onset of the decision
    threshold.
    This function can be used also to test the
    correctness of a channel/station metadata on a set of traces
    representing recordings from that channel/station

    :param traces: an iterable of ObsPy Traces (e.g., list of trace, or ObsPy
        Stream object). Tocompute the PSD features of a single trace, pass
        the 1-element list `[trace]`.
    :param metadata: the trace metadata (Obspy Inventory object), usually
        obtained by calling `read_inventory` on a given StationXML file
        (https://www.fdsn.org/xml/station/)

    :return: the amplitude anomaly score in [0, 1] (1=anomaly). NaN values
        denotes undecided outcome, i.e. when the score could not be computed
        (errors or NaN during PSD computation)
    '''
    psd_values = tracefeat(traces, metadata)
    return featscore(psd_values, check_nan=True)


def tracefeat(traces, metadata):
    '''Computes the (1-dimensional) feature space for any given ObsPy Traces,
    element-wise. The feature is the PSD in decibels at 5 seconds. The returned
    value can be used as input in `featscore` to compute the traces anomaly
    scores, also element-wise.

    :param traces: an iterable of ObsPy Traces (e.g., list of trace, or ObsPy
        Stream object). Tocompute the PSD features of a single trace, pass
        the 1-element list `[trace]`.
    :param metadata: the traces metadata (Obspy Inventory object), usually
        obtained by calling `read_inventory` on a given StationXML file
        (https://www.fdsn.org/xml/station/)

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
    # in puclic methods
    with redirect(sys.stderr):
        for i, trace in enumerate(traces):
            try:
                values[i, :] = psd_values(FEATURES, trace, metadata)
            except ValueError:
                pass
    return values


def featscore(features, model=None, check_nan=True):
    '''Computes the amplitude anomaly scores from the given feature vectors,
    element wise. Returns a numpy array of anomaly scores in [0, 1], where
    the closer a scores is to 1, the more likely it represents an anomaly.

    :param features: a numpy array of shape [N, M], where M=1 is the
        single feature denoting the PSD (in decibels) computed at 5 seconds
        (PSD@5s). As M=1, an array of length N (i.e., shape (N,)) is also a
        valid argument and will be reshaped internally before classification.
        If `model` is None (i.e., the pre-trained and validated model is used),
        the features should have been calculated with the function
        `get_features`
    :param model: a scikit.ensemble.IsolationForest, or None. If None, the
        pre-trained model evaluated on a general dataset of seismic waveforms
        will be used
    :param check_nan: boolean (default: True), checks for NaN in features
        and skip their computation: NaNs (numpy.nan) will be returned for these
        elements. If this parameter is False, `features` must not contain
        NaNs, otherwise an Exception is raised
    :return: a numpy array of scores in [0, 1] or NaN (when the
        feature was NaN. Isolation Forest models do not handle NaNs in the
        feature space)
    '''
    if model is None:
        model = DEFAULT_TRAINED_MODEL
        model_fitted = True
    else:
        model_fitted = hasattr(model, "offset_")  # see IsolationForest
        # and check_fitted

    features = _reshape_feature_spaces(features)
    num_instances = features.shape[0]

    if check_nan:
        finite = ~np.isnan(features).any(axis=1)
        num_finite = finite.sum()
        if num_finite < num_instances:
            ret = np.full(num_instances, np.nan, dtype=float)
            if num_finite > 0:
                if not model_fitted:
                    model.fit(features[finite])
                ret[finite] = _featscore(features[finite], model)
            return ret
    if not model_fitted:
        model.fit(features)
    return _featscore(features, model)


def _reshape_feature_spaces(features):
    features = np.asarray(features)
    if len(features.shape) == 1 and len(FEATURES) == 1:
        features = features.reshape((len(features), 1))
    return features


def _featscore(features, model):
    '''Computes the anomaly scores of the Isolation Forest model for the given
    `features` (a numpy matrix of Nx1 elements), element wise. Features must
    NOT be NaN (this is not checked for)
    '''
    return -model.score_samples(features)


def createmodel(n_estimators=100, max_samples=1024, contamination='auto',
                behaviour='new', **kwargs):
    return IsolationForest(n_estimators, max_samples,
                           contamination=contamination,
                           behaviour=behaviour,
                           **kwargs)


@contextmanager
def redirect(src=None, dst=os.devnull):
    '''
    This method prevents Python AND external C shared library to print to stdout/stderr in python,
    preventing also leaking file descriptors.
    If the first argument is None or any object not having a fileno() argument, this
    context manager is simply no-op and will yield and then return

    See (in this order):
    https://stackoverflow.com/a/14797594
    and (final solution modified here):

    Example

    with redirect(sys.stdout):
        print("from Python")
        os.system("echo non-Python applications are also supported")

    :param src: file-like object with a fileno() method. Usually is either `sys.stdout` or
        `sys.stderr`.
    '''

    # some tools (e.g., pytest) change sys.stderr. In that case, we do want this
    # function to yield and return without changing anything
    # Moreover, passing None as first argument means no redirection
    try:
        file_desc = src.fileno()
    except (AttributeError, OSError) as _:
        yield
        return

    # if you want to assert that Python and C stdio write using the same file descriptor:
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
