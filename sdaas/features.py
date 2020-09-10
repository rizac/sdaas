'''
Module for computing model features from ObsPy objects (Traces Streams)

Created on 18 Jun 2020

@author: riccardo
'''
import numpy as np

from sdaas.psd import psd_values


PSD_PERIODS_SEC = (5.,)  # use floats for safety (numpy cast errors?)
FEATURES = tuple(PSD_PERIODS_SEC)


def get_features_from_streams(streams, metadata):
    '''Computes the (1-dimensional) feature space for any given ObsPy Traces,
    element-wise. The feature is the PSD in decibels at 5 seconds. The returned
    value can be used as input in `model.get_score` to compute the traces anomaly
    scores, also element-wise.

    :see:

        :func:`sdaas.features.featappend` to concatenate two feature arrays
            returned from this method

        :func:`sdaas.utils.cli.redirect` for capturing potential external
            C-libraries output:
            ```with redirect(sys.stderr):
                    get_features_from_traces(...)
            ```

    :param streams: an iterable of ObsPy Streams
    :param metadata: the streams metadata (Obspy Inventory object), usually
        obtained by calling `read_inventory` on a given StationXML file
        (https://www.fdsn.org/xml/station/)

    :return: a [M, 1] numpy array of floats representing the feature of the
        given traces, element-wise
    '''
    values = []
    for stream in streams:
        for trace in stream:
            values.append(get_features_from_trace(trace, metadata))
    return np.array(values)


def get_features_from_traces(traces, metadata):
    '''Computes the (1-dimensional) feature space for any given ObsPy Traces,
    element-wise. The feature is the PSD in decibels at 5 seconds. The returned
    value can be used as input in `model.get_score` to compute the traces anomaly
    scores, also element-wise.

    :see:

        :func:`sdaas.features.featappend` to concatenate two feature arrays
            returned from this method

        :func:`sdaas.utils.cli.redirect`for capturing potential external
            C-libraries output:
            ```with redirect(sys.stderr):
                    get_features_from_traces(...)
            ```

    :param traces: an iterable of ObsPy Traces (e.g., iterable of trace, or ObsPy
        Stream object). Tocompute the PSD features of a single trace, pass
        the 1-element list `[trace]`.
    :param metadata: the traces metadata (Obspy Inventory object), usually
        obtained by calling `read_inventory` on a given StationXML file
        (https://www.fdsn.org/xml/station/)

    :return: a [M, 1] numpy array of floats representing the feature of the
        given traces, element-wise
    '''
    values = []
    for trace in traces:
        values.append(get_features_from_trace(trace, metadata))
    return np.array(values)


def get_features_from_trace(trace, metadata):
    '''Computes the (1-dimensional) feature space for any given ObsPy Traces,
    element-wise. The feature is the PSD in decibels at 5 seconds. The returned
    value can be used as input in `featscore` to compute the traces anomaly
    scores, also element-wise.

    :see:

        `featappend` to concatenate two feature arrays returned from this
        method

        :func:`sdaas.utils.cli.redirect` for capturing potential external
            C-libraries output:
            ```with redirect(sys.stderr):
                    get_features_from_trace(...)
            ```

    :param trace: an ObsPy trace.
    :param metadata: the traces metadata (Obspy Inventory object), usually
        obtained by calling `read_inventory` on a given StationXML file
        (https://www.fdsn.org/xml/station/)

    :return: a [1, 1] numpy array of floats representing the feature of the
        given traces, element-wise
    '''
    return psd_values(FEATURES, trace, metadata)


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
