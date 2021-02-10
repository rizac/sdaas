"""
Test the psd calculation used in the fieatures compuation,
The PSD compuation in this package is an optimized version of
ObsPy's counterpart (:class:`obspy.signal.spectral_estimation.PPSD`)

Created on 22 Jun 2020

@author: Riccardo Z. <rizac@gfz-potsdam.de>
"""
import unittest
from os.path import join, dirname

import numpy as np
from obspy.core.stream import read, Stream
from obspy.core.inventory.inventory import read_inventory
from obspy.signal.spectral_estimation import PPSD

from sdaas.core.model import aa_scores
from sdaas.core.features import traces_features


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
                 '&net=TA&sta=A2*&start=2019-01-04T23:22:00&cha=BH?'
                 '&end=2019-01-04T23:24:00'),
                ('http://service.iris.edu/fdsnws/station/1/query?&net=TA'
                 '&sta=A2*&start=2019-01-04T23:22:00&cha=BH?'
                 '&end=2019-01-04T23:24:00&level=response')
            ],
        ):
            # trace, inv = 'GE.FLT1..HH?.mseed', 'GE.FLT1.xml'
            orig_stream = read(file)
            # print([_.get_id() for _ in orig_stream])
            metadata = read_inventory(inv)
            for multip_fact in [-1000, 1, 10000]:
                stream = Stream()
                for t in orig_stream:
                    t = t.copy()
                    t.data *= multip_fact
                    stream.append(t)
                # calculate features but do not capture stderr cause it causes
                # problems with temporarily set output captures:
                feats = traces_features(stream, metadata)
                feats_old = np.asarray([obspyPSD.psd_values([5], _, metadata)
                                        for _ in stream])
                self.assertTrue(np.allclose(feats, feats_old, rtol=rtol,
                                            atol=0, equal_nan=True))
                scores = aa_scores(feats)
                scores_old = aa_scores(feats_old)
                self.assertTrue(np.allclose(scores, scores_old, rtol=rtol,
                                            atol=0, equal_nan=True))
                # test that the current version of psd is the same as our
                # first implementation (copied below in this module):
                feats_old2 = np.asarray([_old_psd_values([5], _, metadata)
                                        for _ in stream])
                assert np.allclose(feats, feats_old2, rtol=1.e-8)


class obspyPSD:
    """container for the old functions used in the paper
    whereby we created the model used in thius package
    The code here is basically the same: call obspy functions directly (
    without optimizations)
    """

    @staticmethod
    def psd_values(periods, raw_trace, inventory):
        periods = np.asarray(periods)
        try:
            ppsd_ = obspyPSD.psd(raw_trace, inventory)
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


def _old_psd_values(psd_periods, tr, metadata, special_handling=None,
                    period_smoothing_width_octaves=1.0,
                    period_step_octaves=0.125, smooth_on_all_periods=False):
    """
    Old implementation of psd_values. See :func:`sdaas.core.psd_values`
    """
    from matplotlib import mlab
    from obspy.signal.util import prev_pow_2
    from obspy.signal.spectral_estimation import dtiny, fft_taper
    import math
    from sdaas.core.psd import _get_response, _setup_yield_period_binning, \
        _yield_period_binning

    # Convert to float, this is only necessary if in-place operations follow,
    # which is the case e.g. for the fft_taper function (see below)
    # (tested with mlab 3.2.2 and obspy 1.1.1)
    tr.data = tr.data.astype(np.float64)

    # if trace has a masked array we fill in zeros
    try:
        tr.data[tr.data.mask] = 0.0
    # if it is no masked array, we get an AttributeError
    # and have nothing to do
    except AttributeError:
        pass

    # merging some PPSD.__init__ stuff here:
    ppsd_length = tr.stats.endtime - tr.stats.starttime  # float, seconds
    stats = tr.stats
    sampling_rate = stats.sampling_rate
    # calculate derived attributes
    # nfft is determined mimicking the fft setup in McNamara&Buland
    # paper:
    # (they take 13 segments overlapping 75% and truncate to next lower
    #  power of 2)
    #  - take number of points of whole ppsd segment (default 1 hour)
    nfft = ppsd_length * sampling_rate
    #  - make 13 single segments overlapping by 75%
    #    (1 full segment length + 25% * 12 full segment lengths)
    nfft = nfft / 4.0
    #  - go to next smaller power of 2 for nfft
    nfft = prev_pow_2(nfft)
    #  - use 75% overlap
    #    (we end up with a little more than 13 segments..)
    nlap = int(0.75 * nfft)

    # calculate the specturm. Using matlab for this seems weird (as the PPSD
    # has a strong focus on outputting plots, it makes sense, here not so much)
    # but the function basically computes an fft and then its power spectrum.
    # (also remember: matlab will be always available as ObsPy dependency)
    spec, _freq = mlab.psd(tr.data, nfft, sampling_rate,
                           detrend=mlab.detrend_linear, window=fft_taper,
                           noverlap=nlap, sides='onesided',
                           scale_by_freq=True)

    # leave out first entry (offset)
    spec = spec[1:]
    freq = _freq[1:]

    # working with the periods not frequencies later so reverse spectrum
    spec = spec[::-1]

    # Here we remove the response using the same conventions
    # since the power is squared we want to square the sensitivity
    # we can also convert to acceleration if we have non-rotational data
    if special_handling == "ringlaser":
        # in case of rotational data just remove sensitivity
        spec /= metadata['sensitivity'] ** 2
    # special_handling "hydrophone" does instrument correction same as
    # "normal" data
    else:
        # determine instrument response from metadata
        try:
            resp = _get_response(tr, metadata, nfft)
        except Exception as e:
            msg = ("Error getting response from provided metadata:\n"
                   "%s: %s\n"
                   "Skipping time segment(s).")
            msg = msg % (e.__class__.__name__, str(e))
            # warnings.warn(msg)
            # return False
            raise ValueError(msg)

        resp = resp[1:]
        resp = resp[::-1]
        # Now get the amplitude response (squared)
        respamp = np.absolute(resp * np.conjugate(resp))
        # Make omega with the same conventions as spec
        w = 2.0 * math.pi * freq
        w = w[::-1]
        # Here we do the response removal
        # Do not differentiate when `special_handling="hydrophone"`
        if special_handling == "hydrophone":
            spec = spec / respamp
        else:
            spec = (w ** 2) * spec / respamp
    # avoid calculating log of zero
    idx = spec < dtiny
    spec[idx] = dtiny

    # go to dB
    spec = np.log10(spec)
    spec *= 10

    # setup variables for the final smoothed spectral values:
    smoothed_psd = []
    _psd_periods = 1.0 / freq[::-1]
    psd_periods = np.asarray(psd_periods)

    if smooth_on_all_periods:
        # smooth the spectrum: for any period P in psd_periods[i] compute a
        # time-dependent range [Pmin, Pmax] around P, and then compute the
        # smoothed spectrum at index i as the mean of spec on [Pmin, Pmax].
        # and computing their mean: for any period P in psd_periods we compute
        # the smoothed spectrum on the period immediately before and after P,
        # we append those two "bounding" values to an array, and we later
        # linearly interpolate the array with our psd_values
        period_bin_centers = []
        period_limits = (_psd_periods[0], _psd_periods[-1])
        # calculate smoothed periods
        for periods_bins in \
                _setup_yield_period_binning(psd_periods,
                                            period_smoothing_width_octaves,
                                            period_step_octaves, period_limits):
            period_bin_left, period_bin_center, period_bin_right = periods_bins
            _spec_slice = spec[(period_bin_left <= _psd_periods) &
                               (_psd_periods <= period_bin_right)]
            smoothed_psd.append(_spec_slice.mean())
            period_bin_centers.append(period_bin_center)
        # interpolate. Use log10 as it was used for training (from tests,
        # linear interpolation does not change much anyway)
        val = np.interp(
            np.log10(psd_periods),
            np.log10(period_bin_centers),
            smoothed_psd
        )
        val[psd_periods < period_bin_centers[0]] = np.nan
        val[psd_periods > period_bin_centers[-1]] = np.nan
    else:
        # the width of frequencies we average over for every bin is controlled
        # by period_smoothing_width_octaves (default one full octave)
        for period_bin_left, period_bin_right in \
                _yield_period_binning(psd_periods,
                                      period_smoothing_width_octaves):
            _spec_slice = spec[(period_bin_left <= _psd_periods) &
                               (_psd_periods <= period_bin_right)]
            smoothed_psd.append(_spec_slice.mean() if len(_spec_slice)
                                else np.nan)

        val = np.array(smoothed_psd)

    return val

if __name__ == "__main__":
    #  import sys;sys.argv = ['', 'Test.testName']
    unittest.main()