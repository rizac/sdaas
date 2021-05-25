"""
Module for computing amplitude anomaly scores using by default
our trained machine learning model based on the
Isolation Forest algorithm:
```
Liu, F. T., Ting, K., and Zhou, Z.-H. (2008). Isolation forest.
In 2008 Eighth IEEE Inter- national Conference on Data Mining, pages 413–422.
```

.. seealso:: :mod:`sdaas.core.features`

Created on 18 Jun 2020

@author: Riccardo Z. <rizac@gfz-potsdam.de>
"""
from os.path import join, dirname

import numpy as np
from joblib import load
# from sklearn.ensemble.iforest import IsolationForest

from sdaas.core.features import (FEATURES, _get_id, traces_idfeatures,
                                 traces_features, streams_idfeatures,
                                 streams_features, trace_features)


def streams_idscores(streams, metadata, idfunc=_get_id):
    """Compute the amplitude anomaly score in [0, 1] from the
    `Traces <https://docs.obspy.org/packages/autogen/obspy.core.trace.Trace.html>_`
    in `streams`, and their identifiers. For details, see :func:`aa_scores`

    :param streams: an iterable of
        `Streams<https://docs.obspy.org/packages/autogen/obspy.core.stream.Stream.html>_`
    :param metadata: the Streams metadata as
        `Inventory object <https://docs.obspy.org/packages/obspy.core.inventory.html>_`
    :param idfunc: the (optional) function `f(trace)` used to get the trace id.
        When None or missing, each trace id will be computed as the tuple
        `(trace_channel_seedID:str, trace_start:datetime, trace_end:datetime)`

    :return: the tuple `(ids, scores)` where, called N the processed traces
        number, `ids` is a list N identifiers and scores is a numpy array of N
        floats in [0, 1], or numpy.nan (if score could not be computed)

    .. seealso:: :func:`aa_scores`
    """
    ids, feats = streams_idfeatures(streams, metadata, idfunc)
    return ids, aa_scores(feats, check_nan=True)


def streams_scores(streams, metadata):
    """Compute the amplitude anomaly score in [0, 1] from the given Streams.
    For details, see :func:`aa_scores`

    :param streams: an iterable of
        `Streams<https://docs.obspy.org/packages/autogen/obspy.core.stream.Stream.html>_`
    :param metadata: the Streams metadata as
        `Inventory <https://docs.obspy.org/packages/obspy.core.inventory.html>_`

    :return: a numpy array of N floats in [0, 1], or numpy.nan (if score could
        not be computed)

    .. seealso:: :func:`aa_scores`
    """
    feats = streams_features(streams, metadata)
    return aa_scores(feats, check_nan=True)


def traces_idscores(traces, metadata, idfunc=_get_id):
    """Compute the amplitude anomaly score in [0, 1] from the given Traces and
    their identifiers. For details on the scores, see :func:`aa_scores`

    :param traces: an iterable of
        `Traces <https://docs.obspy.org/packages/autogen/obspy.core.trace.Trace.html>_`
        like e.g., list, tuple, generator,
        `Stream <https://docs.obspy.org/packages/autogen/obspy.core.stream.Stream.html>_`
    :param metadata: the Traces metadata as
        `Inventory object <https://docs.obspy.org/packages/obspy.core.inventory.html>_`
    :param idfunc: the (optional) function `f(trace)` used to get the trace id.
        When None or missing, each trace id will be computed as the tuple
        `(trace_channel_seedID:str, trace_start:datetime, trace_end:datetime)`

    :return: the tuple `(ids, scores)` where, called N the processed traces
        number, `ids` is a list N identifiers and scores is a numpy array of N
        floats in [0, 1], or numpy.nan (if score could not be computed)

    .. seealso:: :func:`aa_scores`
    """
    ids, feats = traces_idfeatures(traces, metadata, idfunc)
    return ids, aa_scores(feats, check_nan=True)


def traces_scores(traces, metadata):
    """Compute the amplitude anomaly score in [0, 1] from the given Traces.
    For details, see :func:`aa_scores`

    :param traces: an iterable of
        `Trace <https://docs.obspy.org/packages/autogen/obspy.core.trace.Trace.html>_`
        like e.g., list, tuple, generator,
        `Stream <https://docs.obspy.org/packages/autogen/obspy.core.stream.Stream.html>_`
    :param metadata: the Traces metadata as
        `Inventory <https://docs.obspy.org/packages/obspy.core.inventory.html>_`

    :return: a numpy array of N floats in [0, 1], where N is the number of
        processed Traces.  NaN values might be present (meaning: could not
        compute score)

    .. seealso:: :func:`aa_scores`
    """
    feats = traces_features(traces, metadata)
    return aa_scores(feats, check_nan=True)


def trace_score(trace, metadata):
    """Compute the amplitude anomaly score in [0, 1] from the given Trace.
    For details, see :func:`aa_scores`

    :param trace: a
        `Trace <https://docs.obspy.org/packages/autogen/obspy.core.trace.Trace.html>_`
    :param metadata: the Trace metadata as
        `Inventory <https://docs.obspy.org/packages/obspy.core.inventory.html>_`

    :return: a numpy float in [0, 1], or numpy.nan  (if score could not be
        computed)

    .. seealso:: :func:`aa_scores`
    """
    feats = trace_features(trace, metadata)
    return aa_scores(feats, check_nan=True)[0]


def aa_scores(features, model=None, check_nan=True):
    """Compute the amplitude anomaly scores from the given feature vectors,
    element wise. Returns a numpy array of anomaly scores in [0, 1], where
    the closer a scores is to 1, the more likely it represents an anomaly.
    Note however that in the default scenario (`model` is None or missing, i.e.
    use the pre-trained model), we observed scores are returned in the range
    [0.4, 0.8]: scores <=0.5 can be safely considered inliers (i.e., normal
    observations), and - for binary classification - scores > 0.5 need to be
    inspected to determine the onset of the decision threshold.

    :param features: a numpy array of shape [N, M], where M=1 is the
        single feature denoting the PSD (in decibels) computed at 5 seconds
        (PSD@5s). As M=1, an array of length N (e.g., [1, 0.35, ..]) is also a
        valid argument and will be reshaped internally before classification
        (e.g., [[1], [0.35], ..]).
        *IMPORTANT*: If `model` is None (the default and recommended, meaning
        that the pre-trained and validated model is used), the features should
        have been calculated with the functions of this package (see
        :module:`sdaas.core.features` and :module:`sdaas.core.psd`)
    :param model: a :class:`scikit.ensemble.IsolationForest`, or None. If None
        (the default), the pre-trained model evaluated on a general dataset of
        seismic waveforms will be used. See also :func:`create_model`
    :param check_nan: boolean (default: True), checks for NaN in features
        and skip their computation: NaNs (numpy.nan) will be returned for these
        elements. If this parameter is False, `features` must not contain
        NaNs, otherwise an Exception is raised
    :return: a numpy array of N scores in [0, 1] or NaNs (when the
        feature was NaN. Isolation Forest models do not handle NaNs in the
        feature space)
    """
    if model is None:
        model = DEFAULT_TRAINED_MODEL
        if model is None:
            model = load_default_trained_model()
        model_fitted = True
    else:
        model_fitted = hasattr(model, "offset_")  # see IsolationForest
        # and check_fitted

    features = _reshape_feature_space(features)
    num_instances = features.shape[0]

    if check_nan:
        finite = ~np.isnan(features).any(axis=1)
        num_finite = finite.sum()
        if num_finite < num_instances:
            ret = np.full(num_instances, np.nan, dtype=float)
            if num_finite > 0:
                if not model_fitted:
                    model.fit(features[finite])
                ret[finite] = _aa_scores(features[finite], model)
            return ret
    if not model_fitted:
        model.fit(features)
    return _aa_scores(features, model)


def _reshape_feature_space(features):
    features = np.asarray(features)
    if len(features.shape) == 1 and len(FEATURES) == 1:
        features = features.reshape((len(features), 1))
    return features


def _aa_scores(features, model):
    """Compute the anomaly scores of the Isolation Forest model for the given
    `features` (a numpy matrix of Nx1 elements), element wise. Features must
    NOT be NaN (this is not checked for)
    """
    return -model.score_samples(features)


# def create_model(n_estimators=100, max_samples=1024, contamination='auto',
#                  behaviour='new', **kwargs):
#     # IsolationForest might be relatively long to load, import it here
#     # only when needed:
#     from sklearn.ensemble.iforest import IsolationForest
#     return IsolationForest(n_estimators, max_samples,
#                            contamination=contamination,
#                            behaviour=behaviour,
#                            **kwargs)


DEFAULT_TRAINED_MODEL = None


# lazy load DEFAULT_TRAINED_MODEL
def load_default_trained_model():
    global DEFAULT_TRAINED_MODEL
    DEFAULT_TRAINED_MODEL = load(get_model_file_path())
    return DEFAULT_TRAINED_MODEL


def get_model_file_path():
    root_dir = join(dirname(__file__), 'models')
    file_name = ('clf=IsolationForest&'
                 'tr_set=uniform_train.hdf&'
                 'feats=psd@5sec&'
                 'contamination=auto&'
                 'max_samples=4096&'
                 'n_estimators=50&'
                 'random_state=11'
                 '.sklmodel')
    # modify root_dir or file_name according to sklearn version:
    version = _get_sklearn_version_tuple()
    if version is not None:
        if version < (0, 22):
            root_dir = join(root_dir, 'sklearn<0.22.0')
            file_name = ('clf=IsolationForest&' \
                         'tr_set=uniform_train.hdf&'
                         'feats=psd@5sec&'
                         'behaviour=new&'
                         'contamination=auto&'
                         'max_samples=4096&'
                         'n_estimators=50&'
                         'random_state=11'
                         '.sklmodel')
        elif version < (0, 24, 2):
            root_dir = join(root_dir, 'sklearn<0.24.2')

    return join(root_dir, file_name)


def _get_sklearn_version_tuple():
    try:
        from sklearn import __version__
        return tuple(int(_) for _ in __version__.split('.'))
    except (ImportError, ValueError, TypeError):
        return None