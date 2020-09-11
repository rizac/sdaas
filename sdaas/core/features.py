'''
Module for computing model features from ObsPy objects (Traces Streams)

Created on 18 Jun 2020

@author: riccardo
'''
import numpy as np

from sdaas.core.psd import psd_values


PSD_PERIODS_SEC = (5.,)  # use floats for safety (numpy cast errors?)
FEATURES = tuple(PSD_PERIODS_SEC)


def get_streams_features(streams, metadata):
    '''
    Computes the features of all traces in streams

    :param streams: an iterable of
        `Streams <https://docs.obspy.org/packages/autogen/obspy.core.stream.Stream.html>_`
    :param metadata: the streams metadata as
        `Inventory <https://docs.obspy.org/packages/obspy.core.inventory.html>_`

    :return: a N X 1 numpy array of floats representing the traces features
    '''
    values = []
    for stream in streams:
        for trace in stream:
            values.append(get_trace_features(trace, metadata))
    return np.array(values)


def get_streams_idfeatures(streams, metadata):
    '''
    Computes the features of all traces in streams returning also the
    traces identifiers

    :param streams: an iterable of
        `Streams <https://docs.obspy.org/packages/autogen/obspy.core.stream.Stream.html>_`
    :param metadata: the streams metadata as
        `Inventory object <https://docs.obspy.org/packages/obspy.core.inventory.html>_`

    :return: the tuple `(ids, features)`: if N = number of processed traces,
        then ids is a list N identifiers in the for of tuples
        `(trace_id:str, tracs_start:datetime, trace_end:datetime)` and features
        is a N X 1 numpy array of floats representing the traces features
    '''
    values, ids = [], []
    for stream in streams:
        for trace in stream:
            id_, val = get_trace_idfeatures(trace, metadata)
            ids.append(id_)
            values.append(val)
    return ids, np.array(values)


def get_traces_features(traces, metadata):
    '''
    Computes the features of all traces

    :param streams: an iterable of
        `Trace <https://docs.obspy.org/packages/autogen/obspy.core.trace.Trace.html>_`
        including a
        `Stream object<https://docs.obspy.org/packages/autogen/obspy.core.stream.Stream.html>_`
    :param metadata: the streams metadata as
        `Inventory <https://docs.obspy.org/packages/obspy.core.inventory.html>_`

    :return: a N X 1 numpy array of floats representing the traces features
    '''
    values = []
    for trace in traces:
        values.append(get_trace_features(trace, metadata))
    return np.array(values)


def get_traces_idfeatures(traces, metadata):
    '''
    Computes the features of all traces and their identifiers

    :param streams: an iterable of
        `Trace <https://docs.obspy.org/packages/autogen/obspy.core.trace.Trace.html>_`
        including a
        `Stream object<https://docs.obspy.org/packages/autogen/obspy.core.stream.Stream.html>_`
    :param metadata: the traces metadata as
        `Inventory object <https://docs.obspy.org/packages/obspy.core.inventory.html>_`

    :return: the tuple `(ids, features)`: if N = number of processed traces,
        then ids is a list N identifiers in the for of tuples
        `(trace_id:str, tracs_start:datetime, trace_end:datetime)` and features
        is a N X 1 numpy array of floats representing the traces features
    '''
    values, ids = [], []
    for trace in traces:
        id_, val = get_trace_idfeatures(trace, metadata)
        ids.append(id_)
        values.append(val)
    return ids, np.array(values)


def get_trace_features(trace, metadata):
    '''
    Computes the features of the given trace

    :param trace: a
        `Trace <https://docs.obspy.org/packages/autogen/obspy.core.trace.Trace.html>_`
    :param metadata: the streams metadata as
        `Inventory <https://docs.obspy.org/packages/obspy.core.inventory.html>_`

    :return: a 1-length numpy float array of shape (1,) representing the traces
        features.
        NOTE: the features computed from a trace is always a vector (numpy
        arrays) of M scalars: it happens to be M=1 because of the evaluation
        process revealing that a single PSD period produces the best results.
        In general (or in the future with new implementations) M might be > 1
    '''
    return psd_values(FEATURES, trace, metadata)


def get_trace_idfeatures(trace, metadata):
    '''
    Computes the features of the given trace and its identifier

    :param trace: a
        `Trace <https://docs.obspy.org/packages/autogen/obspy.core.trace.Trace.html>_`
    :param metadata: the streams metadata as
        `Inventory <https://docs.obspy.org/packages/obspy.core.inventory.html>_`

    :return: the tuple `(id, features)`: id is a tuple of the form
        `(trace_id:str, tracs_start:datetime, trace_end:datetime)` and features
        is a 1-length numpy float array of shape (1,) representing the traces
        features.
        NOTE: the features computed from a trace is always a vector (numpy
        arrays) of M scalars: it happens to be M=1 because of the evaluation
        process revealing that a single PSD period produces the best results.
        In general (or in the future with new implementations) M might be > 1
    '''
    return _get_id(trace), psd_values(FEATURES, trace, metadata)


def _get_id(trace):
    '''Returns an id from the given trace'''
    # this id uniquely identfies a trace. Note that we could return
    # trace.stats.starttime and trace.stats.endtime (UTCDateTimes)
    # we choose here to provide standard Python classes (potentially loosing
    # nanosecond precision though) which seem to be also more lightweight
    # (almost half of the size, from tests)
    return (trace.get_id(), trace.stats.starttime.datetime,
            trace.stats.endtime.datetime)


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
