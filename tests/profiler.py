"""
Created on 8 Sep 2020

@author: riccardo
"""
from obspy.core.stream import read
import time

from sdaas.core.features import get_trace_features, get_traces_features, featappend, FEATURES,\
    get_streams_features
from sdaas.core.model import get_traces_scores, get_scores, get_streams_scores,\
    get_trace_score
from obspy.core.inventory.inventory import read_inventory
import numpy as np
from os.path import basename
import sys
from sdaas.core.psd import psd_values
from sdaas.cli.utils import redirect


def testperf_mseed():
    """With 100 miniseeds it takes
    around 10 seconds with method 1, 3 and a half seconds with method two"""
    N = 100
    print(f'Loading {N} traces')
    path = '/Users/riccardo/work/gfz/projects/sources/python/sdaas/tests/data/GE.FLT1..HH?.mseed'
    
    metadata = read_inventory('/Users/riccardo/work/gfz/projects/sources/python/sdaas/tests/data/GE.FLT1.xml')

    feats = []
    t = time.time()
    for _ in range(N):
        feats.append(get_traces_scores(read(path), metadata))
        print('a')
    print(f'Read computefeat computescore join: {(time.time() -t)}')
    
    feats = []
    t = time.time()
    for _ in range(N):
        feats = featappend(feats, get_traces_features(read(path), metadata))
    get_scores(feats)
    print(f'Read computefeat join computescore: {(time.time() -t)}')


def funcnoargs(*args, metadata, uzo=False):
    print(f'args: {args}')
    print(f'metadata: {metadata}')

    
def test_attach_custom_attr():
    path = '/Users/riccardo/work/gfz/projects/sources/python/sdaas/tests/data/GE.FLT1..HH?.mseed'
    s = read(path)
    for t in s:
        t.stats.filepath = basename(path)
    asd = 9
    

def _get_features_from_trace(trace, metadata, capture_stderr=False):
    return psd_values(FEATURES, trace, metadata)
    
def _get_features_from_trace_with1(trace, metadata, capture_stderr=False):
    with redirect(sys.stderr if capture_stderr else None):
        return psd_values(FEATURES, trace, metadata)

    
def _get_features_from_trace_with2(trace, metadata, capture_stderr=False):
    if capture_stderr:
        with redirect(sys.stderr if capture_stderr else None):
            return psd_values(FEATURES, trace, metadata)
    return psd_values(FEATURES, trace, metadata)


def testwithstatement_perfs():
    path = '/Users/riccardo/work/gfz/projects/sources/python/sdaas/tests/data/GE.FLT1..HH?.mseed'
    s = read(path)
    metadata = read_inventory('/Users/riccardo/work/gfz/projects/sources/python/sdaas/tests/data/GE.FLT1.xml')
    N = 10
    streams = [s] * N

# This is the same as get_streams_scores:
#     t = time.time()
#     feats = []
#     for stream in streams:
#         for trace in stream:
#             feats.append(get_trace_features(trace, metadata))
#     scores = get_scores(feats)
#     print(f'get_trace_features + get_scores: {(time.time() -t):.2f}')
#     print(scores.shape)

# this is also the same as get_streams_scores:
#     t = time.time()
#     feats = get_streams_features(streams, metadata)
#     scores = get_scores(feats)
#     print(f'get_streams_features + get_scores: {(time.time() -t):.2f}')
#     print(scores.shape)

    import time
    from sdaas.core.features import get_trace_features
    from sdaas.core.model import get_trace_score, get_traces_scores, get_streams_scores,\
        get_scores 
        
    print(f'Computing scores on {N} Streams')
    
    # method 1 (standard)
    t = time.time()
    scores = get_streams_scores(streams, metadata)
    print(f'1)  `get_streams_scores`: {(time.time() -t):.2f}s')
    # print(scores.shape)

    print('To obtain the same results with more control over the loop,\n'
          'check these alternative options:')

    # method 2a (equivelent as the above, with more control over the loop)
    t = time.time()
    feats = []
    for stream in streams:
        for trace in stream:
            feats.append(get_trace_features(trace, metadata))
    scores = get_scores(feats)
    print(f'2a) `get_trace_features` within loop + `get_scores`: {(time.time() -t):.2f}s')
    # print(scores.shape)

    # method 2b (less performant)
    scores = []
    t = time.time()
    for stream in streams:
        scores.extend(get_traces_scores(stream, metadata))
    scores = np.array(scores)
    print(f'2b) `get_traces_score` within loop: {(time.time() -t):.2f}s')
    # print(scores.shape)

    scores = []
    t = time.time()
    for stream in streams:
        for trace in stream:
            scores.append(get_trace_score(trace, metadata))
    scores = np.array(scores)
    print(f'2c) `get_trace_score` within loop: {(time.time() -t):.2f}s')
    # print(scores.shape)


if __name__ == '__main__':
#     testperf_mseed()
#    funcnoargs(1,2,3,metadata=44, False)
#    test_attach_custom_attr()
    testwithstatement_perfs()
