'''Main module implementing the cli (command line interface for computing
seismic waveforms anomaly scores'''

import argparse
from urllib import parse
import sys
import re
import time
import inspect
from random import randrange, shuffle
from datetime import datetime, timedelta
from os.path import isdir, splitext, isfile, join, abspath, basename
from os import listdir
from urllib.error import HTTPError
from requests.exceptions import HTTPError as RequestsHTTPError

import numpy as np

from obspy.core.stream import read
from obspy.core.inventory.inventory import read_inventory
from sdaas.anomalyscore import tracescore
from argparse import RawTextHelpFormatter


# extensions = {
#     '.mseed', '.miniseed', '.hdf', '.h5', '.hdf5', '.he5',
#     '.hdf5', '.hf', 'npz'
# }

fdsn_re = '[a-zA-Z_]+://.+?/fdsnws/(?:station|dataselect)/\\d/query?.*'


class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[32m'  # '\033[92m'
    WARNING = '\033[33m'  # '\033[93m'
    FAIL = '\033[31m'  # '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def process(data, metadata='', threshold=-1.0, colors=True,
            verbose=1, waveform_length=120,
            download_count=5, download_timeout=30,
            **open_kwargs):
    '''
    Computes and prints the amplitude anomaly scores of data, i.e. a score
    in [0, 1] representing how much the recorded amplitude of the
    signal is likely to be an anomaly, or outlier. For binary classification
    problems where the score needs to be converted to the classes "inlier/regular"
    vs. "outlier/anomaly", although it is generally safe to treat
    scores <=0.5 as inliers, experiments revealed that the optimal threshold
    should be evaluated empirically as it is most likely application dependent
    (see also 'threshold').

    :param data: the data to be tested. In conjunction with 'metadata', the
        following combinations of options are valid (note that urls must be
        FDSN compliant with at least the query parameters "net", "sta" and
        "start" provided. For info see https://www.fdsn.org/webservices/):

        To test anomalies in waveform data:
        -----------------------------------
        data:     file (.mseed)
                  directory (this will test all .mseed files in the directory)
                  url (e.g. http://service.iris.edu/fdsnws/dataselect/1/...)
        metadata: file (.xml)
                  url (e.g. http://service.iris.edu/fdsnws/station/1/...)
                  missing/not provided. In this case, 'data' must be an url or
                   a directory containing also a Station XML file (.xml). In
                   any other case (e.g., data is a file), an error is raised

        To test anomalies in metadata:
        ------------------------------
        data:     url (e.g. http://service.iris.edu/fdsnws/station/1/...). The
                   url should have either no "level" query parameter specified,
                   or "level=response". The routine randomly downloads
                   'waveform_count' segments recorded by the station and computes
                   their anomaly score. Scores persistently low (<=0.5) or
                   high (>>0.5) denote "good" or "bad" metadata, respectively.
                   See also parameters 'waveform_count' and 'download_timeout'
        metadata: ignored (if provided, a conflict error is raised)

    :param metadata: the (optional) metadata. as path to a file (Station XML),
        or url. See 'data' argument

    :param threshold: float. When in [0, 1], it sets the decision threshold (DT)
        for classifying data based on their score. A column 'anomaly' will be
        printed with values 0 (False) or 1 (True) for scores <= DT and > DT,
        respectively. The algorithm default theoretical DT is 0.5, which is
        generally ok for a fast estimation, although for a more fine grained
        classification it is best practice to tune and set the optimal DT
        empirically (e.g., in two practical scenarios we observed the optimal
        DT to be between 0.5 and 0.6). Default is -1 (do not set any threshold)

    :param colors: print anomalies in yellow, and regular data in green.
        Ignored if 'threshold' is not set or -1 (the default)

    :param waveform_length: length (in seconds) of the waveforms to download
        and test. Used only when testing anomalies in metadata (see 'data'),
        ignored otherwise. Default: 120

    :param download_count: Maximum number of downloads to attempt while
        fetching waveforms to test. In conjunction with 'download_timeout',
        controls the download execution time. Used only when testing anomalies
        in metadata (see 'data'), ignored otherwise. Default: 5

    :param download_timeout: Maximum time (in seconds) to spend when
        downloading waveforms to test. In conjunction with 'waveform_count',
        controls the download execution time. Used only when testing anomalies
        in metadata (see 'data'), ignored otherwise. Default: 30
    '''
    echo = print
    if not verbose:
        def echo(*args, **kwargs):
            pass
    is_dir = isdir(data)
    # is_station_file = not is_dir and splitext(data)[1].lower() == '.xml'
    is_file = not is_dir and isfile(data)  # splitext(data)[1].lower() == '.mseed'
    is_fdsn = not is_dir and not is_file and re.match(fdsn_re, data)
    is_station_fdsn = is_fdsn and '/station/' in data
    is_dataselect_fdsn = is_fdsn and '/dataselect' in data
    if is_dir:
        files = [abspath(join(data, _)) for _ in listdir(data)
                 if splitext(_)[1].lower() == '.mseed']
        if not files:
            raise FileNotFoundError('No miniseed found (extension: .mseed)')
        iter_stream = (read_data(_) for _ in files)
        if not metadata:
            metadata = [abspath(join(data, _)) for _ in listdir(data)
                        if splitext(_)[1].lower() == '.xml']
            if len(metadata) != 1:
                raise ValueError(f'Expected 1 metadata file (Station XML) in '
                                 f'"{basename(data)}", found {len(metadata)}')
            metadata = metadata[0]
    elif is_file or is_dataselect_fdsn:
        iter_stream = (read_data(_) for _ in [data])
        if not metadata:
            if is_dataselect_fdsn:
                metadata = get_station_metadata_url(get_querydict(data))
            else:
                raise ValueError('"metadata" argument required')
    elif is_station_fdsn:
        if metadata:
            raise ValueError('Conflict: if you input "data" as station '
                             'you can not also provide the "metadata"'
                             'argument')
        metadata = data
        data = get_dataselect_url(get_querydict(metadata))
        iter_stream = download_streams(data, waveform_length,
                                       download_count,
                                       download_timeout)
    else:
        raise ValueError(f'Invalid file/directory/URL path: {data}')
    echo(f'Data    : "{data}"')
    echo(f'Metadata: "{metadata}"')

    inv = read_metadata(metadata)

    echo('Computing anomaly score(s) in [0, 1]:')
    stdout_is_atty = sys.stdout.isatty()
    th_set = 0 <= threshold <= 1
    print_colors = stdout_is_atty and colors and th_set
    endcolor = bcolors.ENDC if print_colors else ''
    color = ''

    echo(f'{"trace":<15} {"start":<19} {"end":<19} {"score":<5}' +
         (f' {"anomaly":<7}' if th_set else ''))
    echo(f'{"-" * 15}+{"-" * 19}+{"-" * 19}+{"-" * 5}' +
         (f'+{"-" * 7}' if th_set else ''))
    for stream in iter_stream:
        scores = tracescore(stream, inv)
        for trace, score in zip(stream, scores):
            if print_colors:
                color = bcolors.OKGREEN if score <= threshold else \
                    bcolors.WARNING  # if score < 0.75 else bcolors.FAIL
            id_, stime_, etime_ = get_id(trace)
            print(f'{id_ : <15} {stime_ : <19} {etime_ : <19} '
                  f'{color}{score : 5.2f}{endcolor}' +
                  (f' {color}{score > threshold: >7d}{endcolor}'
                   if th_set else ''))


def read_metadata(path_or_url):
    try:
        return read_inventory(path_or_url, format="STATIONXML")
    except Exception as exc:
        raise Exception(f'Invalid station (xml) file: {str(exc)}\n'
                        f' (path/url: {path_or_url})')


def read_data(path_or_url):
    try:
        return read(path_or_url, format='MSEED')
    except Exception as exc:
            raise Exception(f'Invalid waveform (mseed) file: {str(exc)}\n'
                            f' (path/url: {path_or_url})')


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
        raise ValueError(f'Can not download waveform: '
                         f'window shorter than {wlen_sec}s')
    wlen = timedelta(seconds=wlen_sec)
    indices = np.random.choice(wcount, wcount, replace=False)
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
            doraise = False
            for _ in str(herr2).split(' '):
                try:
                    code = int(_)
                    if code >= 400 and code < 500:
                        doraise = True
                        break
                except:
                    pass
            if doraise:
                raise
        except Exception as exc:
            pass
        total_time += (time.time() - t)

        if stream is not None and len(stream) and \
                all(len(_.data) for _ in stream):
            yielded += 1
            yield stream
        if yielded >= wmaxcount:
            break
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
#     net, sta, loc, cha = args['net'], args['sta'], args['loc'], args['cha']
#     url = (f"args['URL']?net={net}&sta={sta}&loc={loc}&cha={cha}")
#     if start is None:
#         start = args['start']
#     if end is None:
#         end = args['end']
#     url += f'&start={start.isoformat()}&end={end.isoformat()}'
#     for key, val in additional_args.items():
#         url += f'&{str(key)}={str(val)}'
#     return url


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
            group(1).strip().replace(stripstart, "\n")
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
parser.add_argument('-c',
                    action='store_true' if getdef('colors') else 'store_false',
                    dest='colors',
                    # metavar='colors',  # invalid for store_true action
                    help=getdoc('colors'))
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
args = parser.parse_args()
try:
    sys.exit(process(**vars(args)))
except Exception as exc:
    raise
    print(f'ERROR: {str(exc)}', file=sys.stderr)
    sys.exit(1)
