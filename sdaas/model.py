'''
Created on 18 Jun 2020

@author: riccardo
'''
from os.path import join, dirname

import numpy as np
from joblib import load
from sklearn.ensemble.iforest import IsolationForest

from sdaas.features import FEATURES, get_features_from_traces


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


def get_scores_from_traces(traces, metadata):
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
    psd_values = get_features_from_traces(traces, metadata)
    return get_scores(psd_values, check_nan=True)


def get_scores(features, model=None, check_nan=True):
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
    :param model: a scikit.ensemble.IsolationForest, or None. If None (the
        default), the pre-trained model evaluated on a general dataset of
        seismic waveforms will be used. See also :func:`create_model`
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
                ret[finite] = _get_scores(features[finite], model)
            return ret
    if not model_fitted:
        model.fit(features)
    return _get_scores(features, model)


def _reshape_feature_spaces(features):
    features = np.asarray(features)
    if len(features.shape) == 1 and len(FEATURES) == 1:
        features = features.reshape((len(features), 1))
    return features


def _get_scores(features, model):
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
