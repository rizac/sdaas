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


extensions = {
    '.mseed', '.miniseed', '.hdf', '.h5', '.hdf5', '.he5'

    '.hdf5', '.hf', 'npz'
}

fdsn_re = '[a-zA-Z_]+://.*?/fdsnws/(?:station|dataselect)/\\d/query?.*'


def process(data, metadata, verbose=0,
               metadata_wlen_sec=120,
               metadata_wmaxdownloads=5,
               metadata_wtimeout_sec=120, **open_kwargs):
    echo = print
#     if not verbose:
#         def echo(*args, **kwargs):
#             pass
    is_station = False
    if isdir(data):
        files = [abspath(join(data, _)) for _ in listdir(data)
                 if splitext(_)[1].lower() == '.mseed']
        if not files:
            raise FileNotFoundError('No miniseed found (extension: .mseed)')
        echo(f'Reading from directory, {len(files)} miniseed found')
        iter_stream = (read(_) for _ in files)
        if not metadata:
            metadata = [abspath(join(data, _)) for _ in listdir(data)
                        if splitext(_)[1].lower() == '.xml']
            if len(metadata) != 1:
                raise ValueError(f'Expected 1 metadata file (Station XML) in '
                                 f'"{basename(data)}", found {len(metadata)}')
            metadata = metadata[0]
            echo(f'Using metadata file "{basename(metadata)}"')
    elif not isfile(data):
        if not re.match(fdsn_re, data):
            raise ValueError(f'Invalid file/directory/URL: {data}')
        if '/station/' in data:
            echo(f'Reading metadata from station xml URL, the metadata will '
                 'be tested computing scores of randomly downloaded waveforms')
            is_station = True
            if metadata:
                raise ValueError('Conflict: you cannot input a station URL '
                                 'with the "metadata" argument')
            metadata = data
            iter_stream = download_streams(data, metadata_wlen_sec,
                                           metadata_wmaxdownloads,
                                           metadata_wtimeout_sec)
        else:
            echo(f'Reading data from dataselect URL, the waveform(s) metadata '
                 'will be downloaded accordingly')
            files = [data]
            args = get_querydict(data)
            metadata = get_station_metadata_url(args)
    else:
        echo(f'Reading from miniseed file')
        files = [data]
        iter_stream = (read(_) for _ in files)

    inv = read_metadata(metadata)

    echo(f'{"trace":<15} {"start":<19} {"end":<19} {"score":<5}')
    echo(f'{"-" * 15}+{"-" * 19}+{"-" * 19}+{"-" * 5}')
    for stream in iter_stream:
        scores = from_traces(stream, inv)
        for trace, score in zip(stream, scores):
            if not np.isnan(score) or not is_station:
                start = trace.stats.starttime.datetime
                end = trace.stats.endtime.datetime
                print(f'{trace.get_id() : <15} '
                      f'{start.replace(microsecond=0).isoformat() : <19} '
                      f'{end.replace(microsecond=0).isoformat() : <19} '
                      f'{score : 5.2f}')
                # yield (get_id(trace), score)


def read_metadata(path_or_url):
    try:
        return read_inventory(path_or_url, format="STATIONXML")
    except Exception as exc:
        raise Exception(f'Error reading metadata: {str(exc)}\n'
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


# data = dir. metadata: file or missing. If missing, it must be an xml inside data
# data = file. Then metadata must be present and be a valid xml file
# data = url. Then the metadata might be missing (will be downloaded for any miniseed)

parser = argparse.ArgumentParser(description=('Computes amplitude anomaly '
                                              'scores on waveform data and '
                                              'metadata'))
parser.add_argument('data', metavar='data', type=str,
                    help=('the waveform data. It can be the file path of an '
                          'existing miniSEED, a directory of miniSEEDs, or '
                          'a FDSN-compliant URL of a data web service'))
parser.add_argument('--metadata', '-m', type=str,
                    help='the metadata (station inventory, xml format)')

args = parser.parse_args()
try:
    sys.exit(process(**vars(args)))
except Exception as exc:
    raise
    print(f'ERROR: {str(exc)}', file=sys.stderr)
    sys.exit(1)
