'''Main module implementing the cli (command line interface for computing
seismic waveforms anomaly scores'''

import argparse
from argparse import RawTextHelpFormatter
import sys
import re
import time
import inspect
from datetime import timedelta, datetime
from os.path import isdir, splitext, isfile, join, abspath, basename
from os import listdir
from urllib.error import HTTPError
from requests.exceptions import HTTPError as RequestsHTTPError

import numpy as np
from obspy.core.stream import read
from obspy.core.inventory.inventory import read_inventory

from sdaas.core.features import get_trace_idfeatures
from sdaas.core.model import get_traces_idscores, get_scores
from sdaas.cli.utils import redirect, ansi_colors_escape_codes
from sdaas.cli.fdsn import fdsn_re, get_querydict, get_dataselect_url,\
    get_station_metadata_url


def process(data, metadata='', threshold=-1.0, waveform_length=120,  # in sec
            download_count=5, download_timeout=30,  # in sec
            sep='', verbose=False, capture_stderr=True):
    '''
    Computes and prints the amplitude anomaly scores of each waveform segment
    in 'data'. Anomalies are typically due to artifacts in the data (e.g.
    spikes, zero-amplitude signals) or in the metadata (e.g. stage gain errors).

    The anomaly score is a number in [0, 1] (0: regular waveform or inlier,
    1: anomaly, or outlier) where 0.5 represents the theoretical decision
    threshold T. Note however that in the practice scores are returned roughly
    in the range [0.4, 0.8]: scores <= 0.5 can be safely considered as inliers,
    and - for binary classification - scores > 0.5 might need inspection to
    determine the optimal T (see also parameter 'threshold').

    Each waveform will be printed as a row of a tabular output with columns
    "waveform_id" "waveform_start" "waveform_end" "anomaly_score" and
    optionally "anomaly" (see 'threshold' argument)

    :param data: the data to be tested. In conjunction with 'metadata', the
        following combinations of options are valid (note that urls below must
        be FDSN compliant with at least the query parameters "net", "sta" and
        "start" provided. For info see https://www.fdsn.org/webservices/):

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
                  url should have either no "level" query parameter specified,
                  or "level=response". The routine randomly downloads
                  segments recorded by the station and computes their anomaly
                  score (see parameters 'download_count', 'waveform_length' and
                  'download_timeout'). Scores persistently low (<=0.5) or
                  high (>>0.5) denote "good" or "bad" metadata, respectively
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
    '''
    separator = sep
    sort_by_time = True
    echo = print
    if not verbose:
        def echo(*args, **kwargs):
            pass
    is_dir = isdir(data)
    is_file = not is_dir and isfile(data)  # splitext(data)[1].lower() == '.mseed'
    is_fdsn = not is_dir and not is_file and re.match(fdsn_re, data)
    is_station_fdsn = is_fdsn and '/station/' in data
    is_dataselect_fdsn = is_fdsn and '/dataselect' in data
    filenames = None
    if is_dir:
        filenames = [_ for _ in listdir(data)
                     if splitext(_)[1].lower() == '.mseed']
        if not filenames:
            raise FileNotFoundError('No miniseed found (extension: .mseed)')
        iter_stream = (read_data(abspath(join(data, _))) for _ in filenames)
        if not metadata:
            metadata = [abspath(join(data, _)) for _ in listdir(data)
                        if splitext(_)[1].lower() == '.xml']
            if len(metadata) != 1:
                raise ValueError(f'Expected 1 metadata file (Station XML) in '
                                 f'"{basename(data)}", found {len(metadata)}')
            metadata = metadata[0]
    elif is_file or is_dataselect_fdsn:
        iter_stream = (read_data(_) for _ in [data])
        if is_file:
            filenames = [basename(data)]
        if not metadata:
            if is_dataselect_fdsn:
                metadata = get_station_metadata_url(get_querydict(data))
            else:
                raise ValueError('"metadata" argument required')
    elif is_station_fdsn:
        if metadata:
            raise ValueError('Conflict: if you input "data" as station url '
                             'you can not also provide the "metadata"'
                             'argument')
        # normalize metadata URL (e.g., add level=response, endtime=now etcetera):
        metadata = get_station_metadata_url(get_querydict(data))
        data = get_dataselect_url(get_querydict(metadata))
        iter_stream = download_streams(data, waveform_length, download_count,
                                       download_timeout)
    else:
        raise ValueError(f'Invalid file/directory/URL path: {data}')
    echo(f'Data    : "{data}"')
    echo(f'Metadata: "{metadata}"')

    inv = read_metadata(metadata)

    # echo('Computing anomaly score(s) in [0, 1]:')
    echo('Results (columns: waveform_id, waveform_start_time, '
         'waveform_end_time, anomaly_score'
         f"{', anomaly' if is_threshold_set(threshold) else ''}"
         '):')

    max_traceid_len = 2 + 5 + 2 + 3 + 3  # default trace id length
    with redirect(sys.stderr if capture_stderr else None):
        if filenames is None:
            # iterate over each stream and print result
            # immediately: we could get all streams and then compute their
            # scores once, which is faster, but not in this case as we are
            # downloading from the web. Also, printing results as-we-get-it
            # it's nicer for the user whoi can start check scores while waiting
            for stream in iter_stream:
                ids, scores = get_traces_idscores(stream, inv)
                for (id_, st_, et_), score in zip(ids, scores):
                    if not separator:  # align left
                        id_ += ' ' * max(0, max_traceid_len - len(id_))
                    print_result(id_, st_, et_, score, threshold, separator)
        else:
            max_traceid_len += len(max(filenames, key=len)) + 1
            # Here we can compute the streams scores once,
            # which is the fastest:
            # `ids, scores = get_streams_idscores(iter_stream, inv)`
            # but we need to keep track of the file names and the mapping
            # filename <-> trace is 1 to N. So, we could then compute
            # scores in a for loop:
            # `get_get_traces_idscores` (as above), which is the slowest.
            # We have a halfway solution: compute features in a
            # loop, and then scores all at once
            feats = []
            ids = []
            for fname, stream in zip(filenames, iter_stream):
                for trace in stream:
                    (id_, st_, et_), feat = get_trace_idfeatures(trace, inv)
                    feats.append(feat)
                    id_ = f'{fname}/{id_}'
                    if not separator:  # align left
                        id_ += ' ' * max(0, max_traceid_len - len(id_))
                    ids.append((id_, st_, et_))
            scores = get_scores(np.asarray(feats))
            # now sort (if needed) and print them at once:
            iter_ = zip(ids, scores)
            if sort_by_time:
                iter_ = sorted(iter_, key=lambda _: _[0][1])
            for id_, score in iter_:
                print_result(*id_, score, threshold, separator)


def print_result(trace_id: str, trace_start: datetime, trace_end: datetime,
                 score: float, threshold: float = None,
                 separator: str = None):
    '''prints a classification result form a single trace'''
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
        trace_start = f'{trace_start.isoformat(" "):<26}'
        trace_end = f'{trace_end.isoformat(" "):<26}'
    else:
        # format for CSV
        trace_start = f'{trace_start.isoformat()}'
        trace_end = f'{trace_end.isoformat()}'

    sep = separator or '  '
    print(
        f'{trace_id}{sep}{trace_start}{sep}{trace_end}{sep}{score_str}'
        f'{sep if outlier_str else ""}{outlier_str}'
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


# def get_id(trace):
#     '''
#     Returns the ID of the given trace as tuple (id, starttime, endtime)
# 
#     :return: the tuple of strings (id, starttime, endtime), where id is in the
#     form 'net.sta.loc.cha' and  starttime and endtime are ISO formatted
#     date-time strings
#     '''
#     start, end = trace.stats.starttime.datetime, trace.stats.endtime.datetime
#     # round start and end: first add 1 second and then use .replace (see below)
#     if start.microsecond >= 500000:
#         start = start + timedelta(seconds=1)
#     if end.microsecond >= 500000:
#         end = end + timedelta(seconds=1)
#     return (trace.get_id(),
#             start.replace(microsecond=0).isoformat(),
#             end.replace(microsecond=0).isoformat())


def download_streams(station_url, wlen_sec, wmaxcount, wtimeout_sec):
    args = get_querydict(station_url)
    yielded = 0
    total_time = 0
    start, end = args['start'], args['end']
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
            yield stream
#         if yielded >= wmaxcount:
#             break
        if total_time > wtimeout_sec:
            timeout_expired = True
            break

    if not yielded:
        raise ValueError(('No waveform data found in the specified period, '
                          'check URL parameters. ') +
                         (f'Timeout ({wtimeout_sec} s) exceeded'
                          if timeout_expired else ''))


def getdoc(param=None):
    '''
    Parses the doc of the `process` function and returns the doc for the
    given param. If the latter is None, returns the doc for the whole
    function (portion of text from start until first occurrence of ":param "
    '''
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

if __name__ == '__main__':
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

    # parse arguments and pass them to `process`
    # (here we see why names must match):
    args = parser.parse_args()
    try:
        process(**vars(args))
        sys.exit(0)
    except Exception as exc:
        raise
        print(f'ERROR: {str(exc)}', file=sys.stderr)
        sys.exit(1)
