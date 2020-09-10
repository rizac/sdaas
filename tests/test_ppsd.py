'''
Created on 22 Jun 2020

@author: riccardo
'''
import unittest
from os.path import join, dirname

import numpy as np
from obspy.core.stream import read, Stream
from obspy.core.inventory.inventory import read_inventory
from obspy.signal.spectral_estimation import PPSD

from sdaas.model import get_scores
from sdaas.features import get_features_from_traces


class Test(unittest.TestCase):


    def setUp(self):
        pass


    def tearDown(self):
        pass


    def test_ppsd(self):
        '''tests that the psd with the algorithm used in this module
        and the original evaluation algorithm (see _old class) produce the same
        results with scores that do not differ by more than 0.01 (roughly)
        '''
        rtol = 1e-2
        dataroot = join(dirname(__file__), 'data')
        for file, inv in (
            [
                join(dataroot, 'trace_GE.APE.mseed'),
                join(dataroot, 'inventory_GE.APE.xml')
            ],
            [
                join(dataroot, 'GE.FLT1..HH?.mseed'),
                join(dataroot, 'GE.FLT1.xml')
            ],
            [
                ('http://service.iris.edu/fdsnws/dataselect/1/query?'
                 '&net=TA&sta=A*&start=2019-01-04T23:22:00&cha=BH?'
                 '&end=2019-01-04T23:24:00'),
                ('http://service.iris.edu/fdsnws/station/1/query?&net=TA'
                 '&sta=A*&start=2019-01-04T23:22:00&cha=BH?'
                 '&end=2019-01-04T23:24:00&level=response')
            ],
        ):
            # trace, inv = 'GE.FLT1..HH?.mseed', 'GE.FLT1.xml'
            orig_stream = read(file)
            metadata = read_inventory(inv)
            for multip_fact in [-1000, 1, 10000]:
                stream = Stream()
                for t in orig_stream:
                    t = t.copy()
                    t.data *= multip_fact
                    stream.append(t)
                # calculate features but do not capture stderr cause it causes
                # problems with temporarily set output captures:
                feats = get_features_from_traces(stream, metadata)
                feats_old = np.asarray([_old.psd_values([5], _, metadata)
                                        for _ in stream])
                self.assertTrue(np.allclose(feats, feats_old, rtol=rtol,
                                            atol=0, equal_nan=True))
                scores = get_scores(feats)
                scores_old = get_scores(feats_old)
                self.assertTrue(np.allclose(scores, scores_old, rtol=rtol,
                                            atol=0, equal_nan=True))


class _old:
    '''container for the old functions used in the paper
    whereby we created the model used in thius package
    The code here is basically the same: call obspy functions directly (
    without optimizations)
    '''

    @staticmethod
    def psd_values(periods, raw_trace, inventory):
        periods = np.asarray(periods)
        try:
            ppsd_ = _old.psd(raw_trace, inventory)
        except Exception as esc:
            raise ValueError('%s error when computing PSD: %s' %
                             (esc.__class__.__name__, str(esc)))
        # check first if we can interpolate ESPECIALLY TO SUPPRESS A WEIRD
        # PRINTOUT (numpy?): something like '5064 5062' which happens
        # on IndexError (len(ppsd_.psd_values)=0)
        if not len(ppsd_.psd_values):
            raise ValueError('Expected 1 psd array, no psd computed')
        val = np.interp(
            np.log10(periods),
            np.log10(ppsd_.period_bin_centers),
            ppsd_.psd_values[0]
        )
        val[periods < ppsd_.period_bin_centers[0]] = np.nan
        val[periods > ppsd_.period_bin_centers[-1]] = np.nan
        return val

    @staticmethod
    def psd(raw_trace, inventory):
        # tr = segment.stream(True)[0]
        dt = raw_trace.stats.endtime - raw_trace.stats.starttime  # total_seconds
        ppsd = PPSD(raw_trace.stats, metadata=inventory, ppsd_length=int(dt))
        ppsd.add(raw_trace)
        return ppsd


if __name__ == "__main__":
    #  import sys;sys.argv = ['', 'Test.testName']
    unittest.main()