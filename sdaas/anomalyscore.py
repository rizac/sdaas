'''
Created on 18 Jun 2020

@author: riccardo
'''
import numpy as np
from os import listdir
from os.path import join, dirname, splitext

from joblib import load

from sdaas.psd import psd_values
from sklearn.ensemble.iforest import IsolationForest


PSD_PERIODS_SEC = (5.,)  # use floats for safety (numpy cast errors?)
FEATURES = tuple(PSD_PERIODS_SEC)
MODEL_FILENAME = [f for f in listdir(dirname(__file__))
                  if splitext(f)[1] == '.sklmodel']
assert len(MODEL_FILENAME) == 1
if_supervised_model = load(join(dirname(__file__), MODEL_FILENAME[0]))


def from_traces(traces, metadata):
    '''Computes the amplitude anomaly score in [0, 1] from the given ObsPy
    Traces element wise. The closer a scores is to 1, the more likely it
    represents an anomaly. This function can be tested also to test the
    correctness of a channel/station metadata on a set of traces
    representing recordings from that channel/station

    :param traces: an iterable of ObsPy Traces (e.g., list of trace, or ObsPy
        Stream object). Tocompute the PSD features of a single trace, pass
        the 1-element list `[trace]`.
    :param metadata: the trace metadata (Obspy Inventory object), usually
        obtained by calling `read_inventory` on a given StationXML file
        (https://www.fdsn.org/xml/station/)

    :return: the amplitude anomaly score in [0, 1] (1=anomaly). A value > 1
        denotes undecided outcome, i.e. when the score could not be computed
    '''
    psd_values = get_features(traces, metadata)
    return from_features(psd_values, check_nan=True)


def get_features(traces, metadata):
    '''Computes the (single) feature from the given ObsPy Traces element
    wise. The feature is the PSD in decibels at 5 seconds. The returned value
    can be used as input in `from_psd_values` to compute the traces anomaly
    scores, element wise.

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
    for i, trace in enumerate(traces):
        try:
            values[i, :] = psd_values(FEATURES, trace, metadata)
        except ValueError:
            pass
    return values


def from_features(features, model=None, check_nan=True):
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
        model = if_supervised_model
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
                ret[finite] = _from_features(features[finite])
            return ret
    if not model_fitted:
        model.fit(features)
    return _from_features(features, model)


def _reshape_feature_spaces(features):
    features = np.asarray(features)
    if len(features.shape) == 1 and len(FEATURES) == 1:
        features = features.reshape((len(features), 1))
    return features


def _from_features(features, model):
    '''Computes the anomaly scores of the Isolation Forest model for the given
    `features` (a numpy matrix of Nx1 elements), element wise. Features must
    NOT be NaN (this is not checked for)
    '''
    return -model.score_samples(features)


def create_model(n_estimators=100, max_samples=1024, contamination='auto',
                 behaviour='new', **kwargs):
    return IsolationForest(n_estimators, max_samples,
                           contamination=contamination,
                           behaviour=behaviour,
                           **kwargs)
