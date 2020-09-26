'''
Implements an optimized version of the power spectral density (PSD) function
of the PPSD module of ObsPy. The function is the feature extractor for our
machine learning model (Ifsolation Forest) for anomaly detection in segments
amplitudes
'''
import math

import numpy as np
from matplotlib import mlab
# AVOID importing from obspy: 1. it's very slow - up to few seconds (py3.7.3
# and obspy 1.2.2. In addition consider that the import of the pre-trained
# scikit model of this package is already quite time consuming, ~=1s).
# 2. It might be a good idea to be free from obspy changes in general, and
# especially in the PSD computation which is very critical as it must be
# exactly the one used for the evaluation. All imported functions have been
# implemented in this module. Refactored packages, changes in the implemenation,
# warnings etcetera are all problems we are happy to avoid.
# In any case, old imports (for info) here:
# from obspy.signal.util import prev_pow_2
# from obspy.signal.spectral_estimation import dtiny, fft_taper
# from obspy.core.inventory.response import Response
# from obspy.core.inventory import Inventory


def psd_values(psd_periods, tr, metadata, special_handling=None,
               period_smoothing_width_octaves=1.0,
               period_step_octaves=0.125, smooth_on_all_periods=False):
    """
    Calculates the power spectral density (PSD) of the given
    trace `tr`, and returns the values in dB at the given `psd_periods`.

    Note: If used to compute features for the Isolation Forest algorithm,
        all optional parameters should be left as they are,
        as the given parameter where those used for training.
        For any further information, see
        :class:`~obspy.signal.spectral_estimation.PPSD` and
        :meth:`~obspy.signal.spectral_estimation.PPSD.__process`

    :psd_periods: numeric list/array of periods (in second)
    :param tr: obspy Trace
    :param metadata: Response information of instrument. It must be
        a :class:`~obspy.core.inventory.inventory.Inventory` (e.g. read from a
        StationXML file using
        :func:`~obspy.core.inventory.inventory.read_inventory` or fetched
        from a :mod:`FDSN <obspy.clients.fdsn>` webservice)
    :param period_smoothing_width_octaves: float. Determines over
        what period/frequency range the psd is smoothed around every central
        period/frequency. Given in fractions of octaves (default of ``1``
        means the psd is averaged over a full octave at each central
        frequency).
    :param period_step_octaves: float. Ignored if `smooth_on_all_periods` is
        False (the default). Step length on frequency axis in
        fraction of octaves (default of ``0.125`` means one smoothed psd value
        on the frequency axis is measured every 1/8 of an octave).
    :param smooth_on_all_periods: boolean, default False. If True (as used
        during evaluation) compute smoothed psd values (mean over the
        period/frequency range) for each period/frequency of the PSD. Then,
        return the required period/frequencies in `psd_periods` via
        interpolation.
        If False (the default) compute smoothed psd values (mean over the
        period/frequency range) for each required period/frequency
        in `psd_periods`, ignoring `period_step_octaves` and
        interpolation. Note that this means returning slightly different
        values than those used for training, but the error is negligible and
        the method is faster
    """
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


def _get_response(tr, metadata, nfft):
    '''Returns the response from the given trace and the given metadata
    Simplified version of:
    :meth:`~obspy.signal.spectral_estimation.PPSD._get_response`
    (rationale: to optimize the PSD computation, we need to re-implement
    some methods of :class:`~obspy.signal.spectral_estimation.PPSD`)
    '''
    # This function is the same as _get_response_from_inventory
    # but we keep the original PPSd skeleton to show how it
    # might be integrated with new metadata object. For the
    # moment `metadata` must be an Inventory object

    # if isinstance(metadata, Inventory):
    # Note on commented line above: as we want to avoid obspy imports (see
    # comment at the top of the module) we need and alternative solution:
    if hasattr(metadata, 'get_response'):
        return _get_response_from_inventory(tr, metadata, nfft)
#         elif isinstance(self.metadata, Parser):
#             return self._get_response_from_parser(tr)
#         elif isinstance(self.metadata, dict):
#             return self._get_response_from_paz_dict(tr)
#         elif isinstance(self.metadata, (str, native_str)):
#             return self._get_response_from_resp(tr)
#     else:
#         msg = "Unexpected type for `metadata`: %s" % type(self.metadata)
#         raise TypeError(msg)
    msg = "Unexpected type for `metadata`: %s" % type(metadata)
    raise TypeError(msg)


def _get_response_from_inventory(tr, metadata, nfft):
    '''Replaces
    :meth:`~obspy.signal.spectral_estimation.PPSD._get_response_from_inventory`
    (rationale: to optimize the PSD computation, we need to re-implement
    some methods of :class:`~obspy.signal.spectral_estimation.PPSD`)
    '''
    inventory = metadata
    delta = 1.0 / tr.stats.sampling_rate
    id_ = "%(network)s.%(station)s.%(location)s.%(channel)s" % tr.stats
    response = inventory.get_response(id_, tr.stats.starttime)
    # In new ObsPy versions you can uncomment this line:
    # resp, _ = response.get_evalresp_response(t_samp=delta, nfft=nfft,
    #             output="VEL", hide_sensitivity_mismatch_warning=True)
    #
    # For the moment though, `hide_sensitivity_mismatch_warning` is not
    # implemented and we need to creata a hacky solution with
    # wrapping functions in this module:
    resp, _ = get_evalresp_response(response, t_samp=delta, nfft=nfft,
                                    output="VEL")
    return resp


def get_evalresp_response(response, t_samp, nfft, output="VEL",
                          start_stage=None, end_stage=None):
    '''Replaces
    :meth:`~obspy.core.inventory.response.Response.get_evalresp_response`
    (rationale: suppress annoying warning issued from external libraries.
    See :func:`get_evalresp_response_for_frequencies` for details. Note that
    in new ObsPy versions we will be able to remove this function. See
    comments in :func:`_get_response_from_inventory`)
    '''
    # Calculate the output frequencies.
    fy = 1 / (t_samp * 2.0)
    # start at zero to get zero for offset/ DC of fft
    freqs = np.linspace(0, fy, nfft // 2 + 1).astype(np.float64)

    response = get_evalresp_response_for_frequencies(response,
                                                     freqs, output=output,
                                                     start_stage=start_stage,
                                                     end_stage=end_stage)
    return response, freqs


def get_evalresp_response_for_frequencies(response, frequencies, output="VEL",
                                          start_stage=None, end_stage=None):
    '''Replaces
    :meth:`~obspy.core.inventory.response.Response.get_evalresp_response_for_frequencies`
    (rationale: suppress annoying warning issued from external libraries
    by setting explicitly `hide_sensitivity_mismatch_warning=True`. Note that
    in new ObsPy versions we will be able to remove this function. See
    comments in :func:`_get_response_from_inventory`)
    '''
    output, chan = response._call_eval_resp_for_frequencies(
        frequencies, output=output, start_stage=start_stage,
        end_stage=end_stage, hide_sensitivity_mismatch_warning=True)
    return output


def _yield_period_binning(psd_periods, period_smoothing_width_octaves):
    # we step through the period range at step width controlled by
    # period_step_octaves (default 1/8 octave)
    # period_step_factor = 2 ** period_step_octaves

    # the width of frequencies we average over for every bin is controlled
    # by period_smoothing_width_octaves (default one full octave)
    period_smoothing_width_factor = \
        2 ** period_smoothing_width_octaves
    period_smoothing_width_factor_sqrt = \
        (period_smoothing_width_factor ** 0.5)
    for psd_period in psd_periods:
        # calculate left/right edge and center of psd_period bin
        # set first smoothing bin's left edge such that the center frequency is
        # psd_period
        per_left = (psd_period /
                    period_smoothing_width_factor_sqrt)
        per_right = per_left * period_smoothing_width_factor
        yield per_left, per_right


def _setup_yield_period_binning(psd_periods, period_smoothing_width_octaves,
                                period_step_octaves, period_limits):
    """
    Set up period binning, i.e. tuples/lists [Pleft, Pcenter, Pright], from
    `period_limits[0]` up to `period_limits[1]`. Then, for any period P
    in psd_periods, yields the binnings [Pleft1, Pcenter1, Pright1] and
    [Pleft2, Pcenter2, Pright2] such as Pcenter1 <= P <= Pcenter2, and so on.
    The total amount of binnings yielded is always even and
    at most 2 * len(psd_periods)
    """
    if period_limits is None:
        period_limits = (psd_periods[0], psd_periods[-1])
    # we step through the period range at step width controlled by
    # period_step_octaves (default 1/8 octave)
    period_step_factor = 2 ** period_step_octaves
    # the width of frequencies we average over for every bin is controlled
    # by period_smoothing_width_octaves (default one full octave)
    period_smoothing_width_factor = \
        2 ** period_smoothing_width_octaves
    # calculate left/right edge and center of first period bin
    # set first smoothing bin's left edge such that the center frequency is
    # the lower limit specified by the user (or the lowest period in the
    # psd)
    per_left = (period_limits[0] /
                (period_smoothing_width_factor ** 0.5))
    per_right = per_left * period_smoothing_width_factor
    per_center = math.sqrt(per_left * per_right)

    # build up lists
    # per_octaves_left = [per_left]
    # per_octaves_right = [per_right]
    # per_octaves_center = [per_center]
    previous_periods = per_left, per_center, per_right

    idx = np.argwhere(psd_periods > per_center)[0][0]
    psdlen = len(psd_periods)

    # do this for the whole period range and append the values to our lists
    while per_center < period_limits[1] and idx < psdlen:
        # move left edge of smoothing bin further
        per_left *= period_step_factor
        # determine right edge of smoothing bin
        per_right = per_left * period_smoothing_width_factor
        # determine center period of smoothing/binning
        per_center = math.sqrt(per_left * per_right)
        # yield if:
        if previous_periods[1] <= psd_periods[idx] and per_center >= psd_periods[idx]:
            yield previous_periods
            yield per_left, per_center, per_right
            idx += 1

        previous_periods = per_left, per_center, per_right


# =======================================================#
# === Copied obspy utilities to speed up import time === #
# = (see comments at the top of the module for details)  #
# =======================================================#

# from obspy.signal.util.prev_pow_2:


def prev_pow_2(i):
    """
    Find the previous power of two

    >>> prev_pow_2(5)
    4
    >>> prev_pow_2(250)
    128
    """
    # do not use NumPy here, math is much faster for single values
    return int(math.pow(2, math.floor(math.log(i, 2))))


# from obspy.signal.spectral_estimation:

dtiny = np.finfo(0.0).tiny


def fft_taper(data):
    """
    Cosine taper, 10 percent at each end (like done by [McNamara2004]_).

    .. warning::
        Inplace operation, so data should be float.
    """
    data *= cosine_taper(len(data), 0.2)
    return data


# from obspy.signal.invsim:


def cosine_taper(npts, p=0.1, freqs=None, flimit=None, halfcosine=True,
                 sactaper=False):
    """
    Cosine Taper.

    :type npts: int
    :param npts: Number of points of cosine taper.
    :type p: float
    :param p: Decimal percentage of cosine taper (ranging from 0 to 1). Default
        is 0.1 (10%) which tapers 5% from the beginning and 5% form the end.
    :rtype: float NumPy :class:`~numpy.ndarray`
    :return: Cosine taper array/vector of length npts.
    :type freqs: NumPy :class:`~numpy.ndarray`
    :param freqs: Frequencies as, for example, returned by fftfreq
    :type flimit: list or tuple of floats
    :param flimit: The list or tuple defines the four corner frequencies
        (f1, f2, f3, f4) of the cosine taper which is one between f2 and f3 and
        tapers to zero for f1 < f < f2 and f3 < f < f4.
    :type halfcosine: bool
    :param halfcosine: If True the taper is a half cosine function. If False it
        is a quarter cosine function.
    :type sactaper: bool
    :param sactaper: If set to True the cosine taper already tapers at the
        corner frequency (SAC behavior). By default, the taper has a value
        of 1.0 at the corner frequencies.

    .. rubric:: Example

    >>> tap = cosine_taper(100, 1.0)
    >>> tap2 = 0.5 * (1 + np.cos(np.linspace(np.pi, 2 * np.pi, 50)))
    >>> np.allclose(tap[0:50], tap2)
    True
    >>> npts = 100
    >>> p = 0.1
    >>> tap3 = cosine_taper(npts, p)
    >>> (tap3[int(npts*p/2):int(npts*(1-p/2))]==np.ones(int(npts*(1-p)))).all()
    True
    """
    if p < 0 or p > 1:
        msg = "Decimal taper percentage must be between 0 and 1."
        raise ValueError(msg)
    if p == 0.0 or p == 1.0:
        frac = int(npts * p / 2.0)
    else:
        frac = int(npts * p / 2.0 + 0.5)

    if freqs is not None and flimit is not None:
        fl1, fl2, fl3, fl4 = flimit
        idx1 = np.argmin(abs(freqs - fl1))
        idx2 = np.argmin(abs(freqs - fl2))
        idx3 = np.argmin(abs(freqs - fl3))
        idx4 = np.argmin(abs(freqs - fl4))
    else:
        idx1 = 0
        idx2 = frac - 1
        idx3 = npts - frac
        idx4 = npts - 1
    if sactaper:
        # in SAC the second and third
        # index are already tapered
        idx2 += 1
        idx3 -= 1

    # Very small data lengths or small decimal taper percentages can result in
    # idx1 == idx2 and idx3 == idx4. This breaks the following calculations.
    if idx1 == idx2:
        idx2 += 1
    if idx3 == idx4:
        idx3 -= 1

    # the taper at idx1 and idx4 equals zero and
    # at idx2 and idx3 equals one
    cos_win = np.zeros(npts)
    if halfcosine:
        # cos_win[idx1:idx2+1] =  0.5 * (1.0 + np.cos((np.pi * \
        #    (idx2 - np.arange(idx1, idx2+1)) / (idx2 - idx1))))
        cos_win[idx1:idx2 + 1] = 0.5 * (
            1.0 - np.cos((np.pi * (np.arange(idx1, idx2 + 1) - float(idx1)) /
                          (idx2 - idx1))))
        cos_win[idx2 + 1:idx3] = 1.0
        cos_win[idx3:idx4 + 1] = 0.5 * (
            1.0 + np.cos((np.pi * (float(idx3) - np.arange(idx3, idx4 + 1)) /
                          (idx4 - idx3))))
    else:
        cos_win[idx1:idx2 + 1] = np.cos(-(
            np.pi / 2.0 * (float(idx2) -
                           np.arange(idx1, idx2 + 1)) / (idx2 - idx1)))
        cos_win[idx2 + 1:idx3] = 1.0
        cos_win[idx3:idx4 + 1] = np.cos((
            np.pi / 2.0 * (float(idx3) -
                           np.arange(idx3, idx4 + 1)) / (idx4 - idx3)))

    # if indices are identical division by zero
    # causes NaN values in cos_win
    if idx1 == idx2:
        cos_win[idx1] = 0.0
    if idx3 == idx4:
        cos_win[idx3] = 0.0
    return cos_win


# ================================== #
# === end copied obspy utilities === #
# ================================== #
