"""
Implement an optimized version of the power spectral density (PSD) function
of the PPSD module of ObsPy. The function is the feature extractor for our
machine learning model (Isolation Forest) for amplitude anomaly detection in
seismic waveform segments

@author: Riccardo Z. <rizac@gfz-potsdam.de>
"""
import math

import numpy as np
# from matplotlib import mlab
# from obspy.signal.invsim import cosine_taper
from obspy.core.inventory.inventory import Inventory


def trace_psd(tr, metadata,
              psd_periods=None,
              smooth_on_all_periods=False,
              period_smoothing_width_octaves=1.0,
              period_step_octaves=0.125,
              special_handling=None):
    """Calculate the power spectral density (PSD) of the given
    trace `tr`, and returns the values in dB at the given `psd_periods`.

    Note: If used to compute features for the Isolation Forest algorithm,
        all optional parameters should be left as they are,
        as the given parameter where those used for training.
        For any further information, see
        :class:`~obspy.signal.spectral_estimation.PPSD` and
        :meth:`~obspy.signal.spectral_estimation.PPSD.__process`

    :param tr: ObsPy Trace
    :param metadata: Response information of instrument. It must be
        a :class:`~obspy.core.inventory.inventory.Inventory` (e.g. read from a
        StationXML file using
        :func:`~obspy.core.inventory.inventory.read_inventory` or fetched
        from a :mod:`FDSN <obspy.clients.fdsn>` webservice)
    :param psd_periods: numeric list/array of periods (in second) or None.
        At which periods (x axis) the PSD values need to be computed. None
        will return the PSD values and periods without smoothing and
        interpolation. If not None, see argument `smooth_on_all_periods`
    :param smooth_on_all_periods: boolean (default: False). Ignored if
        `psd_periods` is None). If True (as used in ObsPy PPSD), smooth all PSD
        points and then interpolate to return the values at the specified
        `psd_periods`. If False (the default), smooth PSD points only at each
         period of `psd_periods` (generally faster). Smoothing a PSD value at
         a certain frequency (or period in this case) is performed by taking a
         window around the period and returning the mean of the PSDs on that
         window.
    :param period_smoothing_width_octaves: float. Ignored if `psd_periods`
        is None. Determines over what period/frequency range the psd is
        smoothed around every central period/frequency. Given in fractions of
        octaves (default of ``1`` means the psd is averaged over a full octave
        at each central frequency).
    :param period_step_octaves: float (default=0.125). Ignored if `psd_periods`
        is None or `smooth_on_all_periods` is False. Step length on frequency
        axis in fraction of octaves (default of ``0.125`` means one smoothed
        psd value on the frequency axis is measured every 1/8 of an octave)
    :param special_handling: sensor details, for experienced users only. Can
        be `ringlaser', 'hydrophone' or any other value to specify neither of
        the two. Default: None
    """
    # Convert to float, this is only necessary if in-place operations follow,
    # which was the case e.g. for the fft_taper function (see below)
    # (tested with mlab 3.2.2 and obspy 1.1.1. However, fft_taper has been
    # re-implemented here without inplace operations anymore). So comment out
    # the following line for the moment:
    # tr.data = tr.data.astype(np.float64)

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
    #  - go to next smaller power of 2 for nfft:
    nfft = int(math.pow(2, math.floor(math.log(nfft, 2))))
    #  - use 75% overlap
    #    (we end up with a little more than 13 segments..)
    nlap = int(0.75 * nfft)

    # calculate the spectrum. Using matlab for this seems weird (as the PPSD
    # has a strong focus on outputting plots, it makes sense, here not so much)
    # but the function basically computes an fft and then its power spectrum.
    # (also remember: matlab will be always available as ObsPy dependency)
    spec, _freq = psd(tr.data, nfft, sampling_rate, detrend=detrend_linear,
                      window=fft_taper, noverlap=nlap, sides='onesided',
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
    # avoid calculating log of zero (define dtiny here. In obspy's PPSD it was
    # imported from obspy.signal.spectral_estimation):
    dtiny = np.finfo(0.0).tiny
    spec[spec < dtiny] = dtiny

    # go to dB
    spec = np.log10(spec)
    spec *= 10

    # setup variables for the final smoothed spectral values:
    smoothed_psd = []
    _psd_periods = 1.0 / freq[::-1]

    if psd_periods is None:
        return spec, _psd_periods

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

    return val, psd_periods


###################
# PSD COMPUTATION #
###################


def psd(x, nfft=None, fs=None, detrend=None, window=None,
        noverlap=None, pad_to=None, sides=None, scale_by_freq=None):
    r"""
    Compute the power spectral density.

    The power spectral density :math:`P_{xx}` by Welch's average
    periodogram method.  The vector *x* is divided into *NFFT* length
    segments.  Each segment is detrended by function *detrend* and
    windowed by function *window*.  *noverlap* gives the length of
    the overlap between segments.  The :math:`|\mathrm{fft}(i)|^2`
    of each segment :math:`i` are averaged to compute :math:`P_{xx}`.

    If len(*x*) < *NFFT*, it will be zero padded to *NFFT*.

    :param x: 1-D array or sequence. Array or sequence containing the data
    :param fs: float, default: 2. The sampling frequency (samples per time
        unit). It is used to calculate the Fourier frequencies, *freqs*, in
        cycles per time unit.
    :param window: callable or ndarray, default: `.window_hanning`
        A function or a vector of length *NFFT*.  To create window vectors see
        `.window_hanning`, `.window_none`, `numpy.blackman`, `numpy.hamming`,
        `numpy.bartlett`, `scipy.signal`, `scipy.signal.get_window`, etc.  If a
        function is passed as the argument, it must take a data segment as an
        argument and return the windowed version of the segment
    :param sides: {'default', 'onesided', 'twosided'}, optional
        Which sides of the spectrum to return. 'default' is one-sided for real
        data and two-sided for complex data. 'onesided' forces the return of a
        one-sided spectrum, while 'twosided' forces two-sided
    :param pad_to: int, optional. The number of points to which the data
        segment is padded when performing the FFT.  This can be different from
        *NFFT*, which specifies the number of data points used.
        While not increasing the actual resolution of the
        spectrum (the minimum distance between resolvable peaks), this can give
        more points in the plot, allowing for more detail. This corresponds to
        the *n* parameter in the call to fft(). The default is None, which sets
        *pad_to* equal to *NFFT*
    :param nfft: int, default: 256 (also referred to as NFFT - capitalized).
        The number of data points used in each block for the FFT.  A power 2 is
        most efficient.  This should *NOT* be used to get zero padding, or the
        scaling of the result will be incorrect; use *pad_to* for this instead.
    :param detrend: {'none', 'mean', 'linear'} or callable, default: 'none'
        The function applied to each segment before fft-ing, designed to remove
        the mean or linear trend.  Unlike in MATLAB, where the *detrend*
        parameter is a vector, in Matplotlib is it a function.
        The :mod:`~matplotlib.mlab` module defines `.detrend_none`,
        `.detrend_mean`, and `.detrend_linear`, but you can use a custom
        function as well.  You can also use a string to choose one of the
        functions: 'none' calls `.detrend_none`. 'mean' calls `.detrend_mean`.
        'linear' calls `.detrend_linear`.
    :param scale_by_freq : bool, default: True
        Whether the resulting density values should be scaled by the scaling
        frequency, which gives density in units of Hz^-1.  This allows for
        integration over the returned frequency values.  The default is True for
        MATLAB compatibility.
    :param noverlap : int, default: 0 (no overlap)
        The number of points of overlap between segments.

    :return: The tuple `Pxx, freqs` where:
        Pxx (1-D numpy array) are the values for the power spectrum
        :math:`P_{xx}` (real valued), and
        freqs (1-D numpy array) are the frequencies corresponding to the
        elements in *Pxx*

    References
    ----------
    Bendat & Piersol -- Random Data: Analysis and Measurement Procedures, John
    Wiley & Sons (1986)
    """
    Pxx, freqs = _spectral_helper(x=x, y=None, NFFT=nfft, Fs=fs,
                                  detrend_func=detrend, window=window,
                                  noverlap=noverlap, pad_to=pad_to,
                                  sides=sides, scale_by_freq=scale_by_freq,
                                  mode='psd')

    if Pxx.ndim == 2:  # result is a matrix, i.e.
        # Pxx.shape[1] = num of windows (each windowed fft is on one column):
        if Pxx.shape[1] > 1:  # many windows, final fft is the mean:
            Pxx = Pxx.mean(axis=1)
        else:  # only one window, take the (only) windowed fft:
            Pxx = Pxx[:, 0]
    return Pxx.real, freqs


def _spectral_helper(x, y=None, NFFT=None, Fs=None, detrend_func=None,  # noqa
                     window=None, noverlap=None, pad_to=None,  # noqa
                     sides=None, scale_by_freq=None, mode=None):
    """
    Private helper implementing the common parts between the psd, csd
    (cross spectral density), spectrogram and complex, magnitude, angle, and
    phase spectra.
    """
    if y is None:
        # if y is None use x for y
        same_data = True
    else:
        # The checks for if y is x are so that we can use the same function to
        # implement the core of psd(), csd(), and spectrogram() without doing
        # extra calculations.  We return the unaveraged Pxy, freqs, and t.
        same_data = y is x

    if Fs is None:
        Fs = 2
    if noverlap is None:
        noverlap = 0
    if detrend_func is None:
        detrend_func = detrend_none
    if window is None:
        window = window_hanning

    # if NFFT is set to None use the whole signal
    if NFFT is None:
        NFFT = 256  # noqa

    if mode is None or mode == 'default':
        mode = 'psd'
    else:
        lst = ['default', 'psd', 'complex', 'magnitude', 'angle', 'phase']
        if mode not in lst:
            raise ValueError('mode "%s" not in %s' % (str(mode), str(lst)))

    if not same_data and mode != 'psd':
        raise ValueError("x and y must be equal if mode is not 'psd'")

    # Make sure we're dealing with a numpy array. If y and x were the same
    # object to start with, keep them that way
    x = np.asarray(x)
    if not same_data:
        y = np.asarray(y)

    if sides is None or sides == 'default':
        if np.iscomplexobj(x):
            sides = 'twosided'
        else:
            sides = 'onesided'
    else:
        lst = ['default', 'onesided', 'twosided']
        if sides not in lst:
            raise ValueError('sides "%s" not in %s' % (str(sides), str(lst)))

    # zero pad x and y up to NFFT if they are shorter than NFFT
    if len(x) < NFFT:
        n = len(x)
        x = np.resize(x, NFFT)
        x[n:] = 0

    if not same_data and len(y) < NFFT:
        n = len(y)
        y = np.resize(y, NFFT)
        y[n:] = 0

    if pad_to is None:
        pad_to = NFFT

    if mode != 'psd':
        scale_by_freq = False
    elif scale_by_freq is None:
        scale_by_freq = True

    # For real x, ignore the negative frequencies unless told otherwise
    if sides == 'twosided':
        numFreqs = pad_to
        if pad_to % 2:
            freqcenter = (pad_to - 1)//2 + 1
        else:
            freqcenter = pad_to//2
        scaling_factor = 1.
    elif sides == 'onesided':
        if pad_to % 2:
            numFreqs = (pad_to + 1)//2
        else:
            numFreqs = pad_to//2 + 1
        scaling_factor = 2.

    if not np.iterable(window):
        window = window(np.ones(NFFT, x.dtype))
    if len(window) != NFFT:
        raise ValueError(
            "The window length must match the data's first dimension")

    result = stride_windows(x, NFFT, noverlap, axis=0)
    result = detrend(result, detrend_func, axis=0)
    result = result * window.reshape((-1, 1))
    result = np.fft.fft(result, n=pad_to, axis=0)[:numFreqs, :]
    freqs = np.fft.fftfreq(pad_to, 1/Fs)[:numFreqs]

    if not same_data:
        # if same_data is False, mode must be 'psd'
        resultY = stride_windows(y, NFFT, noverlap)
        resultY = detrend(resultY, detrend_func, axis=0)
        resultY = resultY * window.reshape((-1, 1))
        resultY = np.fft.fft(resultY, n=pad_to, axis=0)[:numFreqs, :]
        result = np.conj(result) * resultY
    elif mode == 'psd':
        result = np.conj(result) * result
    elif mode == 'magnitude':
        result = np.abs(result) / np.abs(window).sum()
    elif mode == 'angle' or mode == 'phase':
        # we unwrap the phase later to handle the onesided vs. twosided case
        result = np.angle(result)
    elif mode == 'complex':
        result /= np.abs(window).sum()

    if mode == 'psd':

        # Also include scaling factors for one-sided densities and dividing by
        # the sampling frequency, if desired. Scale everything, except the DC
        # component and the NFFT/2 component:

        # if we have a even number of frequencies, don't scale NFFT/2
        if not NFFT % 2:
            slc = slice(1, -1, None)
        # if we have an odd number, just don't scale DC
        else:
            slc = slice(1, None, None)

        result[slc] *= scaling_factor

        # MATLAB divides by the sampling frequency so that density function
        # has units of dB/Hz and can be integrated by the plotted frequency
        # values. Perform the same scaling here.
        if scale_by_freq:
            result /= Fs
            # Scale the spectrum by the norm of the window to compensate for
            # windowing loss; see Bendat & Piersol Sec 11.5.2.
            result /= (np.abs(window)**2).sum()
        else:
            # In this case, preserve power in the segment, not amplitude
            result /= np.abs(window).sum()**2

    if sides == 'twosided':
        # center the frequency range at zero
        freqs = np.roll(freqs, -freqcenter, axis=0)
        result = np.roll(result, -freqcenter, axis=0)
    elif not pad_to % 2:
        # get the last value correctly, it is negative otherwise
        freqs[-1] *= -1

    # we unwrap the phase here to handle the onesided vs. twosided case
    if mode == 'phase':
        result = np.unwrap(result, axis=0)

    return result, freqs


def stride_windows(x, n, noverlap=None, axis=0):
    """
    Get all windows of x with length n as a single array,
    using strides to avoid data duplication.

    .. warning::

        It is not safe to write to the output array.  Multiple
        elements may point to the same piece of memory,
        so modifying one value may change others.

    Parameters
    ----------
    x : 1D array or sequence
        Array or sequence containing the data.
    n : int
        The number of data points in each window.
    noverlap : int, default: 0 (no overlap)
        The overlap between adjacent windows.
    axis : int
        The axis along which the windows will run.

    References
    ----------
    `stackoverflow: Rolling window for 1D arrays in Numpy?
    <http://stackoverflow.com/a/6811241>`_
    `stackoverflow: Using strides for an efficient moving average filter
    <http://stackoverflow.com/a/4947453>`_
    """
    if noverlap is None:
        noverlap = 0

    if noverlap >= n:
        raise ValueError('noverlap must be less than n')
    if n < 1:
        raise ValueError('n cannot be less than 1')

    x = np.asarray(x)

    if x.ndim != 1:
        raise ValueError('only 1-dimensional arrays can be used')
    if n == 1 and noverlap == 0:
        if axis == 0:
            return x[np.newaxis]
        else:
            return x[np.newaxis].transpose()
    if n > x.size:
        raise ValueError('n cannot be greater than the length of x')

    # np.lib.stride_tricks.as_strided easily leads to memory corruption for
    # non integer shape and strides, i.e. noverlap or n. See #3845.
    noverlap = int(noverlap)
    n = int(n)

    step = n - noverlap
    if axis == 0:
        shape = (n, (x.shape[-1]-noverlap)//step)
        strides = (x.strides[0], step*x.strides[0])
    else:
        shape = ((x.shape[-1]-noverlap)//step, n)
        strides = (step*x.strides[0], x.strides[0])
    return np.lib.stride_tricks.as_strided(x, shape=shape, strides=strides)


#############################
# PSD COMPUTATION (detrend) #
#############################


def detrend(x, key=None, axis=None):
    """
    Return x with its trend removed.

    Parameters
    ----------
    x : array or sequence
        Array or sequence containing the data.

    key : {'default', 'constant', 'mean', 'linear', 'none'} or function
        The detrending algorithm to use. 'default', 'mean', and 'constant' are
        the same as `detrend_mean`. 'linear' is the same as `detrend_linear`.
        'none' is the same as `detrend_none`. The default is 'mean'. See the
        corresponding functions for more details regarding the algorithms. Can
        also be a function that carries out the detrend operation.

    axis : int
        The axis along which to do the detrending.

    See Also
    --------
    detrend_mean : Implementation of the 'mean' algorithm.
    detrend_linear : Implementation of the 'linear' algorithm.
    detrend_none : Implementation of the 'none' algorithm.
    """
    if key is None or key in ['constant', 'mean', 'default']:
        return detrend(x, key=detrend_mean, axis=axis)
    elif key == 'linear':
        return detrend(x, key=detrend_linear, axis=axis)
    elif key == 'none':
        return detrend(x, key=detrend_none, axis=axis)
    elif callable(key):
        x = np.asarray(x)
        if axis is not None and axis + 1 > x.ndim:
            raise ValueError(f'axis(={axis}) out of bounds')
        if (axis is None and x.ndim == 0) or (not axis and x.ndim == 1):
            return key(x)
        # try to use the 'axis' argument if the function supports it,
        # otherwise use apply_along_axis to do it
        try:
            return key(x, axis=axis)
        except TypeError:
            return np.apply_along_axis(key, axis=axis, arr=x)
    else:
        raise ValueError(
            f"Unknown value for key: {key!r}, must be one of: 'default', "
            f"'constant', 'mean', 'linear', or a function")


def detrend_mean(x, axis=None):
    """
    Return x minus the mean(x).

    Parameters
    ----------
    x : array or sequence
        Array or sequence containing the data
        Can have any dimensionality

    axis : int
        The axis along which to take the mean.  See numpy.mean for a
        description of this argument.

    See Also
    --------
    detrend_linear : Another detrend algorithm.
    detrend_none : Another detrend algorithm.
    detrend : A wrapper around all the detrend algorithms.
    """
    x = np.asarray(x)

    if axis is not None and axis+1 > x.ndim:
        raise ValueError('axis(=%s) out of bounds' % axis)

    return x - x.mean(axis, keepdims=True)


def detrend_none(x, axis=None):
    """
    Return x: no detrending.

    Parameters
    ----------
    x : any object
        An object containing the data

    axis : int
        This parameter is ignored.
        It is included for compatibility with detrend_mean

    See Also
    --------
    detrend_mean : Another detrend algorithm.
    detrend_linear : Another detrend algorithm.
    detrend : A wrapper around all the detrend algorithms.
    """
    return x


def detrend_linear(y):
    """
    Return x minus best fit line; 'linear' detrending.

    Parameters
    ----------
    y : 0-D or 1-D array or sequence
        Array or sequence containing the data

    axis : int
        The axis along which to take the mean.  See numpy.mean for a
        description of this argument.

    See Also
    --------
    detrend_mean : Another detrend algorithm.
    detrend_none : Another detrend algorithm.
    detrend : A wrapper around all the detrend algorithms.
    """
    # This is faster than an algorithm based on linalg.lstsq.
    y = np.asarray(y)

    if y.ndim > 1:
        raise ValueError('y cannot have ndim > 1')

    # short-circuit 0-D array.
    if not y.ndim:
        return np.array(0., dtype=y.dtype)

    x = np.arange(y.size, dtype=float)

    C = np.cov(x, y, bias=1)
    b = C[0, 1]/C[0, 0]

    a = y.mean() - b*x.mean()
    return y - (b*x + a)


####################
# TAPERING WINDOWS #
####################


def fft_taper(data):
    """Cosine taper, 10 percent at each end (like done by [McNamara2004]).
    Re-implements obspy.signal.spectral_estimation.fft_taper to avoid inplace
    operations (not necessary here)
    """
    return data * cosine_taper(len(data), 0.2)


def cosine_taper(npts, p=0.1, freqs=None, flimit=None, halfcosine=True,
                 sactaper=False):
    """
    Cosine Taper. Copied from ObsPy to avoid importing unnecessary stuff from
    the invsim module (import in ObsPy can be quite slow)

    :param npts: int. Number of points of cosine taper.
    :param p: float. Decimal percentage of cosine taper (ranging from 0 to 1).
        Default is 0.1 (10%) which tapers 5% from the beginning and 5% form the
        end.
    :param freqs: :class:`~numpy.ndarray`. Frequencies
    :param flimit: list or tuple of floats. The list or tuple defines the four
        corner frequencies (f1, f2, f3, f4) of the cosine taper which is one
        between f2 and f3 and tapers to zero for f1 < f < f2 and f3 < f < f4.
    :param halfcosine: bool. If True the taper is a half cosine function. If
        False it is a quarter cosine function.
    :param sactaper: bool. If set to True the cosine taper already tapers at
        the corner frequency (SAC behavior). By default, the taper has a value
        of 1.0 at the corner frequencies.

    :return: Cosine taper array/vector of length npts (:class:`~numpy.ndarray`)
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


def window_hanning(x):
    """
    Return x times the hanning window of len(x).

    See Also
    --------
    window_none : Another window algorithm.
    """
    return np.hanning(len(x))*x


# def window_none(x):
#     """
#     No window function; simply return x.
#
#     See Also
#     --------
#     window_hanning : Another window algorithm.
#     """
#     return x


##########################
# RESPONSE-RELATED STUFF #
##########################


def _get_response(tr, metadata, nfft):
    """Return the response from the given trace and the given metadata
    Simplified version of:
    :meth:`~obspy.signal.spectral_estimation.PPSD._get_response`
    (rationale: to optimize the PSD computation, we need to re-implement
    some methods of :class:`~obspy.signal.spectral_estimation.PPSD`)
    """
    # This function is the same as _get_response_from_inventory
    # but we keep the original PPSd skeleton to show how it
    # might be integrated with new metadata object. For the
    # moment `metadata` must be an Inventory object
    if isinstance(metadata, Inventory):
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
    """Alias of
    :meth:`~obspy.signal.spectral_estimation.PPSD._get_response_from_inventory`
    (rationale: to optimize the PSD computation, we need to re-implement
    some methods of :class:`~obspy.signal.spectral_estimation.PPSD`)
    """
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
    """Alias of
    :meth:`~obspy.core.inventory.response.Response.get_evalresp_response`
    (rationale: suppress annoying warning issued from external libraries.
    See :func:`get_evalresp_response_for_frequencies` for details. Note that
    in new ObsPy versions we will be able to remove this function. See
    comments in :func:`_get_response_from_inventory`)
    """
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
    """Alias of
    :meth:`~obspy.core.inventory.response.Response.get_evalresp_response_for_frequencies`
    (rationale: suppress annoying warning issued from external libraries
    by setting explicitly `hide_sensitivity_mismatch_warning=True`. Note that
    in new ObsPy versions we will be able to remove this function. See
    comments in :func:`_get_response_from_inventory`)
    """
    output, chan = response._call_eval_resp_for_frequencies(
        frequencies, output=output, start_stage=start_stage,
        end_stage=end_stage, hide_sensitivity_mismatch_warning=True)
    return output


#################################
# SMOOTHING WINDOWS COMPUTATION #
#################################


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
    """Set up period binning, i.e. tuples/lists [Pleft, Pcenter, Pright], from
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
