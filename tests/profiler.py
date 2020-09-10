'''
Created on 8 Sep 2020

@author: riccardo
'''
from obspy.core.stream import read
import time

from sdaas.features import get_features_from_traces, featappend, FEATURES
from sdaas.model import get_scores_from_traces, get_scores
from obspy.core.inventory.inventory import read_inventory
import numpy as np
from os.path import basename
import sys
from sdaas.utils.psd import psd_values
from sdaas.utils.cli import redirect


def testperf_mseed():
    '''With 100 miniseeds it takes
    around 10 seconds with method 1, 3 and a half seconds with method two'''
    N = 100
    print(f'Loading {N} traces')
    path = '/Users/riccardo/work/gfz/projects/sources/python/sdaas/tests/data/GE.FLT1..HH?.mseed'
    
    metadata = read_inventory('/Users/riccardo/work/gfz/projects/sources/python/sdaas/tests/data/GE.FLT1.xml')

    feats = []
    t = time.time()
    for _ in range(N):
        feats.append(get_scores_from_traces(read(path), metadata))
        print('a')
    print(f'Read computefeat computescore join: {(time.time() -t)}')
    
    feats = []
    t = time.time()
    for _ in range(N):
        feats = featappend(feats, get_features_from_traces(read(path), metadata))
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
    N = 100

    t = time.time()
    for _ in range(N):
        for tr in s:
            _get_features_from_trace(tr, metadata)
    print(f'get_features_from_trace: {(time.time() -t)}')

    t = time.time()
    for _ in range(N):
        for tr in s:
            _get_features_from_trace_with1(tr, metadata)
    print(f'get_features_from_trace_with1: {(time.time() -t)}')

    t = time.time()
    for _ in range(N):
        for tr in s:
            _get_features_from_trace_with2(tr, metadata)
    print(f'get_features_from_trace_with2: {(time.time() -t)}')


if __name__ == '__main__':
#     testperf_mseed()
#    funcnoargs(1,2,3,metadata=44, False)
#    test_attach_custom_attr()
    testwithstatement_perfs()
