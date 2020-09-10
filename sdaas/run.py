'''Main module implementing the cli (command line interface for computing
seismic waveforms anomaly scores'''

import argparse
from argparse import RawTextHelpFormatter
from urllib import parse
import sys
import re
import time
import inspect
from random import randrange
from datetime import datetime, timedelta
from os.path import isdir, splitext, isfile, join, abspath, basename
from os import listdir
from urllib.error import HTTPError
from requests.exceptions import HTTPError as RequestsHTTPError

import numpy as np
from obspy.core.stream import read
from obspy.core.inventory.inventory import read_inventory

from sdaas.model import get_scores_from_traces, get_scores
from sdaas.features import get_features_from_trace
from sdaas.utils.cli import redirect, ansi_colors_escape_codes

# extensions = {
#     '.mseed', '.miniseed', '.hdf', '.h5', '.hdf5', '.he5',
#     '.hdf5', '.hf', 'npz'
# }

fdsn_re = '[a-zA-Z_]+://.+?/fdsnws/(?:station|dataselect)/\\d/query?.*'


def process(data, metadata='', threshold=-1.0,
            waveform_length=120,  # in seconds
            download_count=5, download_timeout=30,  # in seconds
            sep='',
            verbose=0,
            capture_stderr=True,
            **open_kwargs):
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

    :param threshold: decision threshold T. When in [0, 1], scores > T
        will be classified as anomaly (and thus scores<=T as regular data), and
        an additional column 'anomaly' with values 0 (False) or 1 (True) will
        be shown. The algorithm default theoretical T=0.5 is generally ok for
        a fast estimation, although for a more fine grained classification we
        suggest to tune and set the optimal T empirically (e.g., in two use
        benchmark cases we observed the optimal T to be between 0.5 and 0.6).
        Default is -1 (do not set the decision threshold). If a threshold
        is set, the 'sep' argument is not provided and the terminal supports
        color, then scores will be colored according to the derived class

    :param sep: the column separator. Because each waveform is printed as a
        row of a tabular output with columns "id" "start" "end" "score" and
        optionally "anomaly" (see 'threshold' argument), you might want to set
        explicitly the column separator. For instance to print CSV-formatted
        output, set 'sep' to, comma "," or  semicolon ";" . Default is the
        empty string, meaning that 'sep' is computed each time to align columns
        and provide a more readable output). If this argument is set, nothing
        will be printed in colors

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

    max_traceid_len = 3 + 5 + 2 + 3  # default trace id length
    with redirect(None if not capture_stderr else sys.stderr):
        if filenames is None:
            for stream in iter_stream:
                scores = get_scores_from_traces(stream, inv)
                for trace, score in zip(stream, scores):
                    id_, st_, et_ = get_id(trace)  # @UnusedVariable
                    if not separator:  # align left
                        id_ += ' ' * max(0, max_traceid_len - len(id_))
                    print_result(id_, st_, et_, score, threshold, separator)
        else:
            feats = []
            ids = []
            max_traceid_len += len(max(filenames, key=len)) + 1
            for fname, stream in zip(filenames, iter_stream):
                for trace in stream:
                    feats.append(get_features_from_trace(trace, inv))
                    id_, st_, et_ = get_id(trace)  # @UnusedVariable
                    id_ = f'{fname}/{id_}'
                    if not separator:  # align left
                        id_ += ' ' * max(0, max_traceid_len - len(id_))
                    ids.append((id_, st_, et_))
            scores = get_scores(np.asarray(feats))
            iter_ = zip(ids, scores)
            if sort_by_time:
                iter_ = sorted(iter_, key=lambda _: _[0][1])
            for id_, score in iter_:
                print_result(*id_, score, threshold, separator)


def print_result(trace_id: str, trace_start: str, trace_end: str,
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

        # bcolors.FAIL
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


def get_id(trace):
    '''Returns the ID of the given trace as tuple (id, starttime, endtime)

    :return: the tuple of strings (id, starttime, endtime), where id is in the
    form 'net.sta.loc.cha' and  starttime and endtime are ISO formatted
    date-time strings
    '''
    start, end = trace.stats.starttime.datetime, trace.stats.endtime.datetime
    # round start and end: first add 1 second and then use .replace (see below)
    if start.microsecond >= 500000:
        start = start + timedelta(seconds=1)
    if end.microsecond >= 500000:
        end = end + timedelta(seconds=1)
    return (trace.get_id(),
            start.replace(microsecond=0).isoformat(),
            end.replace(microsecond=0).isoformat())


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


def random_datetime(start, end):
    """
    This function will return a random datetime between two datetime
    objects.
    """
    total_sec = int((end - start).total_seconds())
    if total_sec < 1:
        raise ValueError('start and end time must be greater than 1 second')
    return start + timedelta(seconds=randrange(total_sec))


# minimum requirements: net, sta, start time (uniquely identifying a station)

def get_querydict(url):
    url_splitted = parse.urlsplit(url)
    # object above is of the form:
    # ParseResult(scheme='http', netloc='www.example.org',
    #             path='/default.html', query='ct=32&op=92&item=98',
    #             fragment='')
    # now parse its query. Note that each element is a LIST!
    # (arguments might appear more times)
    queryargs = parse.parse_qs(url_splitted.query)
    # mandatory arguments:
    ret = {
        'net': get_url_arg(queryargs, url, "net", "network"),
        'sta': get_url_arg(queryargs, url, "sta", "station"),
        'start': get_url_datetime_arg(queryargs, url, 'start', 'starttime')
    }
    # optional arguments
    for params in [("loc", "location"), ("cha", "channel")]:
        try:
            ret[params[0]] = get_url_arg(queryargs, url, *params)
        except KeyError:
            pass
    # in case of end,if missing, set now as endtime:
    try:
        ret['end'] = get_url_datetime_arg(queryargs, url, 'end', 'endtime')
    except KeyError:
        ret['end'] = datetime.utcnow().replace(microsecond=0)
    # little check:
    if ret['start'] >= ret['end']:
        raise ValueError('Invalid "start" >= "end": {url}')
    # add base URL:
    ret['URL'] = (f'{url_splitted.scheme}://{url_splitted.netloc}'
                  f'{url_splitted.path}')
    return ret


def get_dataselect_url(querydict, start=None, end=None):
    return get_url(querydict, start, end).\
        replace('/station/', '/dataselect/')


def get_station_metadata_url(querydict, start=None, end=None):
    return get_url(querydict, start, end, level='response').\
        replace('/dataselect/', '/station/')


def get_url(querydict, start=None, end=None, **additional_args):
    args = dict(querydict)
    args['start'] = (start or args['start']).isoformat()
    args['end'] = (end or args['end']).isoformat()
    args = {**args, **additional_args}
    url = args.pop('URL') + '?'
    for key, val in args.items():
        url += f'&{str(key)}={str(val)}'
    return url


def get_url_datetime_arg(query_dict, url, *keys):
    val = get_url_arg(query_dict, url, *keys)
    try:
        return datetime.fromisoformat(val)
    except Exception:
        raise ValueError(f'Invalid date/time for "{"/".join(keys)}" '
                         f'in {url}')


def get_url_arg(query_dict, url, *keys):
    for key in keys:
        if key in query_dict:
            val = query_dict[key]
            if len(val) > 1:
                raise ValueError(f'Invalid multiple values for '
                                 f'"{"/".join(keys)}" in {url}')
            return val[0]
    raise KeyError(f'Missing parameter "{"/".join(keys)}" in {url}')


def getdoc(param=None):
    '''Parses the doc of the process function and returns the doc for the
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
    parser.add_argument('-m',  # <- optional argument
                        type=type(getdef('metadata')),
                        default=getdef('metadata'),
                        dest='metadata',
                        metavar='metadata',
                        help=getdoc('metadata'))
    parser.add_argument('-th',
                        type=type(getdef('threshold')),
                        default=getdef('threshold'),
                        dest='threshold',
                        metavar='threshold',
                        help=getdoc('threshold'))
    parser.add_argument('-sep',
                        default=getdef('sep'),
                        dest='sep',
                        metavar='sep',
                        help=getdoc('sep'))
    parser.add_argument('-wl',  # <- optional argument
                        type=type(getdef('waveform_length')),
                        default=getdef('waveform_length'),
                        dest='waveform_length',
                        metavar='waveform_length',
                        help=getdoc('waveform_length'))
    parser.add_argument('-dc',  # <- optional argument
                        type=type(getdef('download_count')),
                        default=getdef('download_count'),
                        dest='download_count',
                        metavar='download_count',
                        help=getdoc('download_count'))
    parser.add_argument('-dt',  # <- optional argument
                        type=type(getdef('download_timeout')),
                        default=getdef('download_timeout'),
                        dest='download_timeout',
                        metavar='download_timeout',
                        help=getdoc('download_timeout'))
    parser.add_argument('-v',
                        action='store_false' if getdef('verbose') else 'store_true',
                        dest='verbose',
                        # metavar='colors',  # invalid for store_true action
                        help=getdoc('verbose'))
    args = parser.parse_args()
    try:
        process(**vars(args))
        sys.exit(0)
    except Exception as exc:
        # raise
        print(f'ERROR: {str(exc)}', file=sys.stderr)
        sys.exit(1)
