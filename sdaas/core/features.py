'''
Module for computing model features from ObsPy objects (Traces Streams).
The features will be used as input of our model to compute the traces
anomaly scores

.. seealso:: :mod:`module`

Created on 18 Jun 2020

@author: riccardo
'''
import numpy as np

from sdaas.core.psd import psd_values


PSD_PERIODS_SEC = (5.,)  # use floats for safety (numpy cast errors?)
FEATURES = tuple(PSD_PERIODS_SEC)


def _get_id(trace):
    '''Returns the default id from a given trace'''
    # this id uniquely identfies a trace. Note that we could return
    # trace.stats.starttime and trace.stats.endtime (UTCDateTimes)
    # we choose here to provide standard Python classes (potentially loosing
    # nanosecond precision though) which seem to be also more lightweight
    # (almost half of the size, from tests)
    return (trace.get_id(), trace.stats.starttime.datetime,
            trace.stats.endtime.datetime)


def get_streams_features(streams, metadata):
    '''
    Computes the features of all
    `Traces <https://docs.obspy.org/packages/autogen/obspy.core.trace.Trace.html>_`
     in `streams`

    :param streams: an iterable of
        `Streams <https://docs.obspy.org/packages/autogen/obspy.core.stream.Stream.html>_`
    :param metadata: the streams metadata as
        `Inventory <https://docs.obspy.org/packages/obspy.core.inventory.html>_`

    :return: a N X 1 numpy array of floats representing the N one-dimensional
        feature vectors, where N is the total number of processed traces

    .. seealso:: :func:`get_trace_features`
    '''
    values = []
    for stream in streams:
        for trace in stream:
            values.append(get_trace_features(trace, metadata))
    return np.array(values)


def get_streams_idfeatures(streams, metadata, idfunc=_get_id):
    '''
    Computes the features of all
    `Traces<https://docs.obspy.org/packages/autogen/obspy.core.trace.Trace.html>_`
    in `streams` returning also the traces identifiers

    :param streams: an iterable of
        `Streams <https://docs.obspy.org/packages/autogen/obspy.core.stream.Stream.html>_`
    :param metadata: the streams metadata as
        `Inventory object <https://docs.obspy.org/packages/obspy.core.inventory.html>_`
    :param idfunc: the (optional) function `f(trace)` used to get the trace id.
        When None or missing, each trace id will be computed as the tuple
        `(trace_channel_seedID:str, trace_start:datetime, trace_end:datetime)`

    :return: the tuple `(ids, features)` where, called N the processed traces
        number, ids is a list N identifiers and features is a N X 1 numpy array
        of floats representing the N one-dimensional feature vectors

    .. seealso:: :func:`get_trace_idfeatures`
    '''
    values, ids = [], []
    for stream in streams:
        for trace in stream:
            id_, val = get_trace_idfeatures(trace, metadata, idfunc)
            ids.append(id_)
            values.append(val)
    return ids, np.array(values)


def get_traces_features(traces, metadata):
    '''
    Computes the features of all traces

    :param streams: an iterable of
        `Trace <https://docs.obspy.org/packages/autogen/obspy.core.trace.Trace.html>_`
        including also the
        `Stream object<https://docs.obspy.org/packages/autogen/obspy.core.stream.Stream.html>_`
    :param metadata: the streams metadata as
        `Inventory <https://docs.obspy.org/packages/obspy.core.inventory.html>_`

    :return: a N X 1 numpy array of floats representing the N one-dimensional
        feature vectors, where N is the total number of processed Traces

    .. seealso:: :func:`get_trace_features`
    '''
    values = []
    for trace in traces:
        values.append(get_trace_features(trace, metadata))
    return np.array(values)


def get_traces_idfeatures(traces, metadata, idfunc=_get_id):
    '''
    Computes the features of all traces and their identifiers

    :param streams: an iterable of
        `Trace <https://docs.obspy.org/packages/autogen/obspy.core.trace.Trace.html>_`
        including also the
        `Stream object<https://docs.obspy.org/packages/autogen/obspy.core.stream.Stream.html>_`
    :param metadata: the traces metadata as
        `Inventory object <https://docs.obspy.org/packages/obspy.core.inventory.html>_`
    :param idfunc: the (optional) function `f(trace)` used to get the trace id.
        When None or missing, each trace id will be computed as the tuple
        `(trace_channel_seedID:str, trace_start:datetime, trace_end:datetime)`

    :return: the tuple `(ids, features)` where, called N the processed traces
        number, ids is a list N identifiers and features is a N X 1 numpy array
        of floats representing the N one-dimensional feature vectors

    .. seealso:: :func:`get_trace_idfeatures`
    '''
    values, ids = [], []
    for trace in traces:
        id_, val = get_trace_idfeatures(trace, metadata, idfunc)
        ids.append(id_)
        values.append(val)
    return ids, np.array(values)


def get_trace_features(trace, metadata):
    '''
    Computes the features of the given trace.
    Note that the outcome of the Feature selection employed for identifying the
    best combination of features resulted in a single feature among all PSD
    periods inspected (PSD computed at 5s period). Consequently, our feature
    space has dimenion 1 and each trace feature vector is returned as a
    1-length numpy array of shape (1,)

    :param trace: a
        `Trace <https://docs.obspy.org/packages/autogen/obspy.core.trace.Trace.html>_`
    :param metadata: the streams metadata as
        `Inventory <https://docs.obspy.org/packages/obspy.core.inventory.html>_`

    :return: a 1-length numpy float array of shape (1,) representing the trace
        features vector
    '''
    return psd_values(FEATURES, trace, metadata)


def get_trace_idfeatures(trace, metadata, idfunc=_get_id):
    '''
    Computes the features of the given trace and its identifier.
    Note that the outcome of the Feature selection employed for identifying the
    best combination of features resulted in a single feature among all PSD
    periods inspected (PSD computed at 5s period). Consequently, our feature
    space has dimenion 1 and each trace feature vector is returned as a
    1-length numpy array of shape (1,)

    :param trace: a
        `Trace <https://docs.obspy.org/packages/autogen/obspy.core.trace.Trace.html>_`
    :param metadata: the streams metadata as
        `Inventory <https://docs.obspy.org/packages/obspy.core.inventory.html>_`
    :param idfunc: the (optional) function `f(trace)` used to get the trace id.
        When None or missing, the trace id will be computed as the tuple
        `(trace_channel_seedID:str, trace_start:datetime, trace_end:datetime)`

    :return: the tuple `(id, features)` where id is the trace id and features
        is a numpy array of length 1 representing the trace features vector
    '''
    return idfunc(trace), psd_values(FEATURES, trace, metadata)


def featappend(features1, features2):
    '''Calls numpy.append(features1, features2) and works also if one
    inputs Nones or empty arrays.

    .. seealso:: :func:`get_features_from_traces` or :func:`get_features_from_streams`

    :param features1: a Nx1 array of features, e.g. the output of
        :func:`get_features_from_traces` or :func:`get_features_from_streams`.
        None or the empty list/ tuple / numpy arrays are also valid
    :param features2: another Mx1 array. See `features1` for details

    :return features1 + features2 in a single (N + M) x 1 array
    '''
    flen = len(FEATURES)

    if features1 is None or not len(features1):
        features1 = np.full(shape=(0, flen), fill_value=np.nan)
    if features2 is None or not len(features2):
        features2 = np.full(shape=(0, flen), fill_value=np.nan)

    return np.append(features1, features2, axis=0)
