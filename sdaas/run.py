"""cli (command line interface) module of the program

@author: Riccardo Z. <rizac@gfz-potsdam.de>
"""

import argparse
from argparse import RawTextHelpFormatter
from collections import defaultdict
import sys
import re
import time
import inspect
from typing import TextIO
from io import StringIO
import warnings
from datetime import timedelta, datetime
from os.path import isdir, splitext, isfile, join, abspath, basename
from os import listdir
from urllib.error import HTTPError
from requests.exceptions import HTTPError as RequestsHTTPError

import numpy as np
from obspy.core.stream import read
from obspy.core.inventory.inventory import read_inventory

from sdaas.core.features import trace_idfeatures
from sdaas.core.model import aa_scores, load_default_trained_model
from sdaas.cli.utils import ansi_colors_escape_codes, ProgressBar
from sdaas.cli.fdsn import get_querydict, get_dataselect_url,\
    get_station_url, is_fdsn_dataselect_url, is_fdsn, get_station_urls, \
    datetime_fromisoformat


def process(data, metadata='', threshold=-1.0, aggregate='',
            waveform_length=120,  # in sec
            download_count=5, download_timeout=30,  # in sec
            sep='', verbose=False):
    """Compute and prints the amplitude anomaly scores of each waveform segment
    in 'data'. Anomalies are typically due to artifacts in the data (e.g.
    spikes, zero-amplitude signals) or in the metadata (e.g. stage gain errors).

    The anomaly score is a number in [0, 1] (0: regular waveform or inlier,
    1: anomaly, or outlier) where 0.5 represents the theoretical decision
    threshold T. Note however that in the practice scores are returned roughly
    in the range [0.4, 0.8]: scores <= 0.5 can be safely considered as inliers,
    and - for binary classification - scores > 0.5 might need inspection to
    determine the optimal T (see also parameter 'threshold').

    Each waveform will be printed to stdout as a row of a tabular output with
    columns
    "waveform_id" "waveform_start" "waveform_end" "anomaly_score"
    and optionally "anomaly" (see 'threshold' argument). The output can be
    redirected to produce e.g, CSV files (see 'sep' argument). In this
    case, note that the progress bar and all additional messages (if 'verbose'
    is on) are printed to stderr and thus not written to file.

    :param data: the data to be tested. In conjunction with 'metadata', the
        following combinations of options are valid (note that urls below must
        be FDSN compliant. For info see https://www.fdsn.org/webservices/):

        To test anomalies in waveform data:
        -----------------------------------
        data:     file (.mseed), or
                  directory (scan and test all .mseed files therein), or
                  url (e.g. http://service.iris.edu/fdsnws/dataselect/1/...)
        metadata: file (.xml), or
                  url (e.g. http://service.iris.edu/fdsnws/station/1/...), or
                  missing/not provided (in this case, 'data' must be an url, or
                  a directory containing also a StationXML file with extension
                  .xml. In any other case an error is raised)

        To test anomalies in metadata:
        ------------------------------
        data:     url (e.g. http://service.iris.edu/fdsnws/station/1/...). The
                  routine fetches all stations requested by the url, and for
                  each station it randomly downloads segments, computing their
                  anomaly score (see parameters 'download_count', 'waveform_length'
                  and 'download_timeout'). For a given station channel, scores
                  persistently low (<=0.5) or high (>>0.5) most likely denote
                  "good" or "bad" metadata, respectively
        metadata: ignored (if provided, a conflict error is raised)

    :param metadata: the metadata, as path to a file (Station XML), or url. See
        the 'data' argument

    :param threshold: decision threshold T. When 0 < T < 1, then scores > T
        will be classified as anomaly (and thus scores<=T as regular data), and
        an additional column 'anomaly' with values 0 (False) or 1 (True) will
        be shown. The algorithm default theoretical T=0.5 is generally ok for
        a fast estimation, although for a more fine grained classification we
        suggest to tune and set the optimal T empirically (e.g., in two use
        cases we observed the optimal T to be between 0.5 and 0.6). Default is
        -1 (do not set the decision threshold). Otherwise, when a threshold is
        given, if the 'sep' argument is not provided and the terminal
        is interactive, then scores will be colored according to the derived
        class (0 or 1)

    :param aggregate: the aggregate function to use (median, mean, min, max).
        If given, each output row will denote a channel (identified by its
        <net.sta.loc.cha> code) and its anomaly score will be the given
        aggregate function computed on all channel's waveforms. The default
        when missing (empty string) means: no aggregation (display one waveform
        per row)

    :param sep: the column separator, particularly useful if the output must be
        redirected to file. E.g., for CSV-formatted output set 'sep' to comma
        "," or  semicolon ";". Default is the empty string, meaning that 'sep'
        is computed each time to align columns and provide a more readable
        output). If this argument is set, nothing will be printed in colors

    :param waveform_length: length (in seconds) of the waveforms to download
        and test. Used only when testing anomalies in metadata (see 'data'),
        ignored otherwise. Default: 120

    :param download_count: maximum number of downloads to attempt while
        fetching waveforms to test. In conjunction with 'download_timeout',
        controls the download execution time. Used only when testing anomalies
        in metadata (see 'data'), ignored otherwise. Default: 5

    :param download_timeout: maximum time (in seconds) to spend when
        downloading waveforms to test. In conjunction with 'waveform_count',
        controls the download execution time. Used only when testing anomalies
        in metadata (see 'data'), ignored otherwise. Default: 30

    :param verbose: (boolean flag) increase verbosity
    """
    separator = sep
    sort_by_time = True

    if not verbose:
        def echo(*args, **kwargs):
            pass
    else:
        def echo(*args, **kwargs):
            print(*args, **kwargs, file=sys.stderr)

    is_dir = isdir(data)
    is_file = not is_dir and isfile(data)  # splitext(data)[1].lower() == '.mseed'
#     is_fdsn = not is_dir and not is_file and re.match(fdsn_re, data)
#     is_station_fdsn = is_statio is_fdsn and '/station/' in data
#     is_dataselect_fdsn = is_fdsn and '/dataselect' in data
#     filepaths = None
    streamiterator = StreamIterator()
    if is_dir:
        streamiterator.add_dir(data, metadata or None)
    elif is_file:
        streamiterator.add_file(data, metadata or None)
    elif is_fdsn(data):
        streamiterator.add_url(data, metadata, waveform_length, download_count,
                               download_timeout)
    else:
        raise ValueError(f'Invalid file/directory/FDSN url: {data}')

    echo(f'Data    : "{data}"')
    echo(f'Metadata: "{metadata}"')

    sio = StringIO()
    kount = 0
    for _ in streamiterator.process(sort_by_time=sort_by_time and not aggregate,
                                    aggregate=aggregate,
                                    progress=sys.stderr,
                                    info=None if not verbose else sys.stderr):
        for id_, score_ in _:
            kount += 1
            print_result(*id_, score_, threshold, separator, file=sio)
    # echo('Computing anomaly score(s) in [0, 1]:')
    if not kount:
        echo('Nothing to process found')
    else:
        sep = separator or ' '
        echo(f'waveform_id{sep}waveform_start{sep}'
             f'waveform_end{sep}anomaly_score'
             f"{sep + 'anomaly' if is_threshold_set(threshold) else ''}")
    out = sio.getvalue().rstrip()  # remove last newline
    if out:
        print(out, file=sys.stdout)
    echo('Done')


def print_result(src: str, trace_id: str, trace_start: datetime,
                 trace_end: datetime, score: float, threshold: float = None,
                 separator: str = None, file: TextIO = sys.stdout):
    """Print a classification result form a single trace"""
    is_file = src and isfile(src)
    if is_file:
        trace_id = join(basename(src), trace_id)
    # left align trace_id column
    if not separator:
        max_traceid_len = 2 + 5 + 2 + 3 + 3  # default traceid length (N.S.L.C)
        if is_file:
            max_traceid_len = 25
        if len(trace_id) > max_traceid_len:
            prefix = '...'
            trace_id = '...' + trace_id[-max_traceid_len+len(prefix):]
        trace_id = ('{:>%d}' % max_traceid_len).format(trace_id)

    score_str = f'{score:4.2f}'
    outlier_str = ''
    th_set = is_threshold_set(threshold)
    if th_set:
        outlier = score > threshold
        outlier_str = f'{outlier:d}'
        if ansi_colors_escape_codes.are_supported_on_current_terminal() \
                and not separator:
            colorstart = ansi_colors_escape_codes.WARNING if outlier else \
                ansi_colors_escape_codes.OKGREEN
            colorend = ansi_colors_escape_codes.ENDC
            score_str = f'{colorstart}{score_str}{colorend}'
            outlier_str = f'{colorstart}{outlier_str}{colorend}'

    if not separator:
        # format for readability:
        trace_start = f'{trace_start.isoformat():<26}'
        trace_end = f'{trace_end.isoformat():<26}'
    else:
        # format for CSV
        trace_start = f'{trace_start.isoformat()}'
        trace_end = f'{trace_end.isoformat()}'

    sep = separator or ' '

    print(
        f'{trace_id}{sep}{trace_start}{sep}{trace_end}{sep}{score_str}'
        f'{sep if outlier_str else ""}{outlier_str}',
        file=file
    )


def is_threshold_set(threshold):
    return 0 < threshold < 1


def read_metadata(path_or_url):
    try:
        return read_inventory(path_or_url, format="STATIONXML")
    except Exception as exc:
        raise Exception(f'Invalid station (xml) file: {str(exc)}\n'
                        f'(path/url: {path_or_url})')


def read_data(path_or_url, format='MSEED', headonly=False, **kwargs):  # @ReservedAssignment
    try:
        return read(path_or_url, format=format, headonly=headonly, **kwargs)
    except Exception as exc:
        raise Exception(f'Invalid waveform (mseed) file: {str(exc)}\n'
                        f'(path/url: {path_or_url})')


class StreamIterator(dict):
    """Class for iterating over given data and metadata arguments, either
    given as files / directory or URLs
    """
    def __init__(self):
        self._data = []

    def add_url(self, url, metadata_path,
                waveform_length, download_count, download_timeout):
        """Add a new FDSN URL, either station or dataselect. In the former
        case, the last three parameters control what segment waveform to
        download, and how
        """
        if is_fdsn_dataselect_url(url):
            metadata_path = get_station_url(get_querydict(url),
                                            level='response')
            self._add_files(url, [url], metadata_path)
            return

        if metadata_path:
            raise ValueError('Conflict: with a station url '
                             'you cannot also provide the "metadata" '
                             'argument')

        # echo(f'{len(station_urls)} station(s) to check')
        # qdic = get_querydict(url)
        for station_url in get_station_urls(url):
            qdic = get_querydict(station_url)
            # normalize metadata URL (e.g., add level=response, endtime=now etcetera):
            metadata_path = get_station_url(qdic, level='response')
            data = get_dataselect_url(qdic)
            iter_stream = download_streams(data, waveform_length,
                                           download_count,
                                           download_timeout)
            self._add_item(station_url, iter_stream, metadata_path,
                           download_count)

    def add_dir(self, path, metadata_path=None):
        """Add a new directory, populated with miniSEED (*.mseed) files

        :param metadata_path: the optional metadata file path  (*.xml). If None
            (the default) the function tries to search it on the given path
        """
        filepaths = [abspath(join(path, _)) for _ in listdir(path)
                     if splitext(_)[1].lower() == '.mseed']
        if not filepaths:
            raise FileNotFoundError('No miniseed found (extension: .mseed)')
        if not metadata_path:
            metadata = [abspath(join(path, _)) for _ in listdir(path)
                        if splitext(_)[1].lower() == '.xml']
            if len(metadata) != 1:
                raise ValueError(f'Expected 1 metadata file (Station XML) in '
                                 f'"{basename(path)}", found {len(metadata)}')
            metadata_path = metadata[0]
        self._add_files(path, filepaths, metadata_path)

    def add_file(self, filepath, metadata_path):
        """Add a miniSEED file with relative metadata path (StationXML)
        """
        if not metadata_path:
            raise ValueError('"metadata" argument required')
        if not isfile(metadata_path):
            raise ValueError('File does not exist: %s' % filepath)
        self._add_files(filepath, [filepath], metadata_path)

    def add_files(self, key, filepaths, metadata_path):
        """Add miniSEED files with relative metadata path (StationXML)"""
        if not filepaths:
            raise FileNotFoundError('No miniseed file provided')
        if not metadata_path:
            raise FileNotFoundError('No metadata (Station XML) file provided')
        if not isfile(metadata_path):
            raise ValueError('No metadata (Station XML) file: %s' %
                             metadata_path)
        self._add_files(key, filepaths, metadata_path)

    def _add_files(self, key, filepaths, metadata_path):
        self._add_item(key, ((_, read_data(_)) for _ in filepaths),
                       metadata_path, len(filepaths))

    def _add_item(self, key, streamiterator, metadata_path, length):
        """streamiterator: an iterator of key, Stream tuples"""
        self._data.append((key, streamiterator, metadata_path, length))

    def process(self, sort_by_time=False,
                aggregate: str or None = None,
                progress: TextIO or None = sys.stderr,
                info: TextIO or None = None):
        """Processes all added files/URLs and yields the results"""
        if aggregate:
            aggregates = ('min', 'max', 'median', 'mean')
            if aggregate not in aggregates:
                raise ValueError(f'"aggregate" not in {str(aggregates)}')

        count, total = 0, sum(_[-1] for _ in self._data)
        data = {}
        messages = None if info is None else []
        # load model now: it takes ~=1 second and is usually lazy loaded,
        # but this means that the progressbar would show misleading results
        # at the beginning
        load_default_trained_model()
        with ProgressBar(progress) as pbar:
            # self._data has generally only one element in the current
            # implementation (see module function `process`), however, it
            # already supports multiple call of its `add_*` methods above
            for key, streamiterator, metadata_path, length in self._data:
                try:
                    inv = read_inventory(metadata_path)
                except Exception as exc:
                    if messages is not None:
                        messages.append(f'Metadata error, {str(exc)}. {key}')
                    streamiterator = []  # hack to skip iteration below

                feats = []
                ids = []
                kount = 0
                try:
                    for fpath, stream in streamiterator:
                        kount += 1
                        for trace in stream:
                            (id_, st_, et_), feat = trace_idfeatures(trace, inv)
                            feats.append(feat)
                            ids.append((fpath, id_, st_, et_))

                except Exception as exc:
                    if messages is not None:
                        messages.append(f'{str(exc)}. {key}')
                        feats = []  # hack to stop after updating the pbar

                count += 1
                pbar.update(count / total)

                if kount < length:
                    count += length - kount
                    pbar.update(count / total)

                if not feats:
                    continue

                scores = aa_scores(np.asarray(feats))

                iter_ = zip(ids, scores)
                if aggregate:
                    data = defaultdict(lambda: [None, []])
                    for (fpath, id_, stime, etime), score in iter_:
                        timeranges, scores_ = data[id_]
                        if not timeranges:
                            data[id_][0] = [stime, etime]
                        else:
                            timeranges[0] = min(stime, timeranges[0])
                            timeranges[1] = max(etime, timeranges[1])
                        scores_.append(score)
                    ids = []
                    scores = []
                    for id_, (timeranges, scores_) in data.items():
                        ids.append(('', id_, *timeranges))
                        scores_ = np.asarray(scores_)
                        if np.isnan(scores_).all():
                            scores.append(np.nan)
                        elif aggregate == 'mean':
                            scores.append(np.nanmean(scores_))
                        elif aggregate == 'min':
                            scores.append(np.nanmin(scores_))
                        elif aggregate == 'max':
                            scores.append(np.nanmax(scores_))
                        else:
                            scores.append(np.nanmedian(scores_))

                    # now sort (if needed) and print them at once:
                    iter_ = zip(ids, scores)

                if sort_by_time:
                    yield sorted(iter_, key=lambda _: _[0][1])
                yield iter_

        for msg in (messages or []):
            print(msg, file=info)


def download_streams(station_url, wlen_sec, wmaxcount, wtimeout_sec):
    args = get_querydict(station_url)
    yielded = 0
    total_time = 0
    start, end = datetime_fromisoformat(args['start']), \
        datetime_fromisoformat(args['end'])
    total_period = end - start
    wcount = int(total_period.total_seconds() / float(wlen_sec))
    if wcount < 1:
        raise ValueError(f'Download period '
                         f'({int(total_period.total_seconds())}s) '
                         f'shorter than download window ({wlen_sec}s)')
    wlen = timedelta(seconds=wlen_sec)
    chunksize = int(wcount / float(wmaxcount))
    indices = np.random.choice(chunksize, wmaxcount, replace=False)
    for i in range(1, len(indices)):
        indices[i] += chunksize * i
    timeout_expired = False

    # finds 0, timeout -> raise Timeout
    # finds any>0, timeout -> ok
    # finds 0, no timeout -> raise not found
    # finds any>0, no timeout -> ok

    for i in indices:
        wstart = start + i * wlen
        dataselect_url = get_dataselect_url(args, start=wstart,
                                            end=wstart+wlen)
        t = time.time()
        stream = None
        try:
            stream = read(dataselect_url)
        # HERE BELOW TRY TO CATCH HTTPERRORS WITH CLIENT CODE (4xx),
        # FOR THESE ERRORS RAISE CAUSE IT's MOST LIKELY SOMETHING TO FIX IN
        # THE URL:
        except HTTPError as herr1:
            if herr1.code >= 400 and herr1.code < 500:
                raise
        except RequestsHTTPError as herr2:
            # hacky workaround: herr2 has all members as None, just the string
            # str(herr2) which is of the form:
            # 400 HTTP Error:  for url: <URL>
            # so le't try to infer the code:
            for _ in str(herr2).split(' '):
                try:
                    code = int(_)
                    if code >= 400 and code < 500:
                        raise herr2 from None
                except ValueError:
                    pass
        except Exception as exc:  # @UnusedVariable
            pass
        total_time += (time.time() - t)

        if stream is not None and len(stream) and \
                all(len(_.data) for _ in stream):
            yielded += 1
            yield dataselect_url, stream

        if total_time > wtimeout_sec:
            timeout_expired = True
            break

    if not yielded:
        raise ValueError(('No waveform data in the specified period, '
                          'check URL parameters. ') +
                         (f'Timeout ({wtimeout_sec} s) exceeded'
                          if timeout_expired else ''))


def getdoc(param=None):
    """Parse the doc of the `process` function and returns the doc for the
    given param. If the latter is None, returns the doc for the whole
    function (portion of text from start until first occurrence of ":param "
    """
    flags = re.DOTALL  # @UndefinedVariable
    pattern = "^(.*?)\\n\\s*\\:param " if not param else \
        f"\\:param {param}: (.*?)(?:$|\\:param)"
    stripstart = "\n    " if not param else "\n        "
    try:
        return re.search(pattern, process.__doc__, flags).\
            group(1).strip().replace(stripstart, "\n") + '\n'
    except AttributeError:
        return 'No doc available'


def getdef(param):
    func = process
    signature = inspect.signature(func)
    val = signature.parameters[param]
    if val.default is not inspect.Parameter.empty:
        return val.default
    raise ValueError(f'"{param}" has no default')


#####################
# ArgumentParser code
#####################

def cli_entry_point():
    parser = argparse.ArgumentParser(
        description=getdoc(),
        formatter_class=RawTextHelpFormatter
    )
    # https://docs.python.org/dev/library/argparse.html#action
    # https://docs.python.org/3/library/argparse.html#argparse.ArgumentParser.add_argument
    parser.add_argument('data',  # <- positional argument
                        type=str,
                        # dest='data',  # invalid for positional argument
                        metavar='data',
                        help=getdoc('data'))
    # optional arguments. Argparse argument here must have a match with
    # an argument of the `process` function above (the match is based on the
    # function name with the names defined below). To implement any new
    # optional argument, provide it in `process` WITH A DEFAULT (mandatory)
    # and a help in the function doc (recommended) and add the argument
    # name here below, with a correponding flag
    for flag, name in [
        ('-m', 'metadata'),
        ('-th', 'threshold'),
        ('-sep', 'sep'),
        ('-agg', 'aggregate'),
        ('-wl', 'waveform_length'),
        ('-dc', 'download_count'),
        ('-dt', 'download_timeout'),
        ('-v', 'verbose')
    ]:
        param_default, param_doc = getdef(name), getdoc(name)
        kwargs = {
            'dest': name,
            'metavar': name,
            'help': param_doc
        }
        if param_default in (True, False):  # boolean flag
            kwargs['action'] = 'store_false' if param_default else 'store_true'
            kwargs.pop('metavar')  # invalid for store_true action
        else:  # no boolean flag
            kwargs['default'] = param_default
            kwargs['type'] = type(param_default)

        # add argument to ArgParse:
        parser.add_argument(flag, **kwargs)

    with warnings.catch_warnings(record=False) as wrn:  # @UnusedVariable
        # Cause all warnings to always be triggered.
        warnings.simplefilter("ignore")
        # parse arguments and pass them to `process`
        # (here we see why names must match):
        args = parser.parse_args()
        try:
            process(**vars(args))
            sys.exit(0)
        except Exception as exc:
            # raise
            print(f'ERROR: {str(exc)}', file=sys.stderr)
            sys.exit(1)


if __name__ == '__main__':
    cli_entry_point()
