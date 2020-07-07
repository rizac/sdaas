import argparse
from urllib import parse
import sys
import re
import time
from random import randrange, shuffle
from datetime import datetime, timedelta
from os.path import isdir, splitext, isfile, join, abspath, basename
from os import listdir
from urllib.error import HTTPError
from requests.exceptions import HTTPError as RequestsHTTPError

import numpy as np

from obspy.core.stream import read
from obspy.core.inventory.inventory import read_inventory
from sdaas.anomalyscore import from_traces
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


def process(data, metadata, verbose=1, metadata_wlen_sec=120,
            metadata_wmaxdownloads=5, metadata_wtimeout_sec=120,
            print_colors=False,
            **open_kwargs):
    '''
    The following options are valid:

    data: directory (will read all .mseed files inside that directory)
    metadata: missing, url, file (if missing, it must be a .xml file inside
        the 'data' directory)

    data: file (.mseed), FDSN_dataselect_url
    metadata: missing, FDSN_station_url, file (if missing, data must be
        a FDSN url so that the FDSN_station_url can be inferred from there)

    data: FDSN_station_url
    metadata: ignored (if provided, a conflict error will be raised)

    URLs must be FDSN compliant, and need at least the query parameters "net",
    "sta" and "start".
    If data is a FDSN station URL it should have the "level=response" parameter
    (or no "level" parameter at all, it will be set automatically). Then, the
    program will test the station metadata by randomly downloading
    'max_segments' station recorded segments and showing their amplitude
    anomaly score: Scores systematically close to 1 might denote errors
    in the station metadata.
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
        iter_stream = download_streams(data, metadata_wlen_sec,
                                       metadata_wmaxdownloads,
                                       metadata_wtimeout_sec)
    else:
        raise ValueError(f'Invalid file/directory/URL path: {data}')
    echo(f'Data (MiniSEED file(s)): "{data}"')
    echo(f'Metadata (Station XML): "{metadata}"')

    inv = read_metadata(metadata)

    echo('Anomaly scores:')
    stdout_is_atty = sys.stdout.isatty()
    print_colors = stdout_is_atty and print_colors
    endcolor = bcolors.ENDC if print_colors else ''
    color = ''
    if print_colors:
        echo(f'{bcolors.BOLD}NOTE: colors provide just a visual hint: they '
             f'represent thresholds derived from theoretical grounds which '
             f'might need to be tuned and re-adjusted depending on the set '
             f'inspected{endcolor}')

    echo(f'{"trace":<15} {"start":<19} {"end":<19} {"score":<5}')
    echo(f'{"-" * 15}+{"-" * 19}+{"-" * 19}+{"-" * 5}')
    for stream in iter_stream:
        scores = from_traces(stream, inv)
        for trace, score in zip(stream, scores):
            # if not np.isnan(score) or not is_station:
            start = trace.stats.starttime.datetime
            end = trace.stats.endtime.datetime
            if print_colors:
                color = bcolors.OKGREEN if score <= 0.5 else \
                    bcolors.WARNING if score < 0.75 else bcolors.FAIL
            print(f'{trace.get_id() : <15} '
                  f'{start.replace(microsecond=0).isoformat() : <19} '
                  f'{end.replace(microsecond=0).isoformat() : <19} '
                  f'{color}{score : 5.2f}{endcolor}')


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
    start, end = trace.stats.starttime, trace.stats.endtime
    return (f'{trace.get_id()} '
            f'{start.datetime.replace(microsecond=0).isoformat()} '
            f'{end.datetime.replace(microsecond=0).isoformat()}')


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
        raise ValueError(('No waveform data found in the specified period, ',
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


parser = argparse.ArgumentParser(
    description=("Computes amplitude anomaly scores on waveform data and "
                 "metadata."),
    epilog=process.__doc__.replace("\\n    ", ""),
    formatter_class=RawTextHelpFormatter
)
parser.add_argument('data', metavar='DATA', type=str,
                    help=('the waveform data. It can be the file path of an '
                          'existing miniSEED, a directory of miniSEEDs, or '
                          'a FDSN-compliant URL of a data web service'))
parser.add_argument('-m', '--metadata', type=str,
                    help='the metadata (station inventory, xml format)')

args = parser.parse_args()
try:
    sys.exit(process(**vars(args)))
except Exception as exc:
    raise
    print(f'ERROR: {str(exc)}', file=sys.stderr)
    sys.exit(1)
