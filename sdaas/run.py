"""cli (command line interface) module of the program

@author: Riccardo Z. <rizac@gfz-potsdam.de>
"""

import argparse
from argparse import RawTextHelpFormatter
from collections import defaultdict
import sys
import re
import inspect
from typing import TextIO
from io import BytesIO
import warnings
from datetime import timedelta, datetime
from os.path import isdir, splitext, isfile, join, abspath, basename
from os import listdir
from urllib import request

import numpy as np
from obspy.core.stream import read
from obspy.core.inventory.inventory import read_inventory

from sdaas.core import traces_scores
from sdaas.core.model import load_default_trained_model
from sdaas.cli.utils import ansi_colors_escape_codes, ProgressBar
from sdaas.cli import fdsn


def process(data, metadata='', threshold=-1.0, aggregate='',
            waveform_length=120,  # in sec
            download_count=5, download_timeout=30,  # in sec
            sep='', verbose=False):
    """Compute and print the amplitude anomaly scores of each waveform segment
    in 'data'. Anomalies are typically due to broken sensor, artifacts in the data
    (e.g. spikes, zero-amplitude signals, unusual noise) or in the metadata (e.g.,
    stage gain errors).

    The anomaly score is a number in [0, 1] (0: regular waveform or inlier,
    1: anomaly, or outlier) where 0.5 represents the theoretical decision
    threshold T. Note however that in the practice scores are returned roughly
    in the range [0.4, 0.8]: scores <= 0.5 can be safely considered as inliers,
    and - for binary classification - scores > 0.5 might need inspection to
    determine the optimal T (see also parameter 'threshold').

    Each waveform will be printed to stdout as a row of a tabular output with
    columns "id" "start" "end" "anomaly_score"
    and optionally "class_label" (see 'threshold' option). The output
    can be redirected to produce e.g, CSV files (see 'sep' option). In this
    case, note that the progress bar and all additional messages (if 'verbose'
    option is set) are printed to stderr and thus not written to file.

    :param data: the data to be tested. In conjunction with 'metadata', the
        following combinations of options are valid (note that urls below must
        be FDSN compliant. For info see https://www.fdsn.org/webservices/):

        To test anomalies in waveform data:
        -----------------------------------
        data:     file (.mseed), or
                  directory (scan and test all .mseed files therein), or
                  url (e.g. http://service.iris.edu/fdsnws/dataselect/1/...)
        metadata: file (.xml), or
                  url (e.g. http://service.iris.edu/fdsnws/station/1/...).
                  If missing, then `data` must be a url or
                  a directory containing also a StationXML file with extension
                  .xml. In any other case an error is raised

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

    :param metadata: the metadata, as path to a file (Station XML), or url. Not
        required in those cases where it can be inferred (see the 'data' argument
        for details)

    :param threshold: decision threshold T. When 0 < T < 1, then scores > T
        will be classified as anomaly (and thus scores<=T as regular data), and
        an additional column 'class_label' with values 0 (inlier) or 1 (outlier)
        will be shown. This parameter defaults to -1 (do not set the decision
        threshold). When given, if the 'sep' option is not provided and the
        terminal is interactive, then scores will be colored according to their
        class label

    :param aggregate: the aggregate function to use (median, mean, min, max).
        Defaults to "" (no aggregation) meaning that each output row represents
        the score of a single waveform. Otherwise, if given, each output row
        will denote a channel (identified by its <net.sta.loc.cha> code) and its
        anomaly score will be the given aggregate function computed on all
        channel's waveforms. The column "anomaly_score" will also be renamed as
        "{aggregate}_anomaly_score" (e.g. "min_anomaly_score")

    :param sep: the column separator, particularly useful if the output must be
        redirected to file. E.g., for CSV-formatted output set 'sep' to comma
        "," or  semicolon ";". Default is " ". If this argument is explicitly
        set, nothing will be printed in colors

    :param waveform_length: length (in seconds) of the waveforms to download
        and test. Used only when testing anomalies in metadata (see `data`
        argument), ignored otherwise. Default: 120

    :param download_count: maximum number of downloads to attempt while
        fetching waveforms to test. In conjunction with 'download_timeout',
        controls the download execution time. Used only when testing anomalies
        in metadata (see `data` argument), ignored otherwise. Default: 5

    :param download_timeout: maximum time (in seconds) to spend when
        downloading waveforms to test. In conjunction with 'waveform_count',
        controls the download execution time. Used only when testing anomalies
        in metadata (see `data` argument), ignored otherwise. Default: 30

    :param verbose: (boolean flag) increase verbosity. When given, additional
        info and errors will be printed to stderr. Also in this case, the
        tabular output header will be printed to stdout instead of stderr,
        which is useful to create CSV files with headers
    """
    separator = sep
    sort_by_time = True

    # Remove URL file prefix from paths (shouldn't be any, but let's be safe):
    file_prefix = "file://"
    if data and data.startswith(file_prefix):
        data = data[len(file_prefix):]
    if metadata and metadata.lower().startswith(file_prefix):
        metadata = metadata[len(file_prefix):]

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
        streamiterator.add_files([data], metadata or None)
    elif is_remote_url(data):
        streamiterator.add_url(data, metadata, waveform_length, download_count)
    else:
        raise ValueError(f'Invalid file/directory/FDSN url: {data}')

    rows = streamiterator.process(sort_by_time=sort_by_time and not aggregate,
                                  aggregate=aggregate,
                                  progressbar_output=sys.stderr,
                                  info_output=None if not verbose else sys.stderr,
                                  download_timeout=download_timeout)
    if rows:
        sep = separator or ' '
        score_caption = 'anomaly_score'
        if aggregate:
            score_caption = f'{aggregate}_{score_caption}'
        th_set = is_threshold_set(threshold)
        print(f'id{sep}start{sep}end{sep}{score_caption}'
              f"{sep + 'class_label' if th_set else ''}",
              file=sys.stderr if not verbose else sys.stdout)
        for row in rows:
            print_result(row['id'], row['start'], row['end'], row[aggregate or 'score'],
                         threshold, separator, file=sys.stdout)


def is_remote_url(path_or_url):
    return "://" in path_or_url  # copied from obspy.core.util.base._generic_reader


def print_result(trace_id: str, trace_start: datetime,
                 trace_end: datetime, score: float, threshold: float = None,
                 separator: str = None, file: TextIO = sys.stdout):
    """Print a classification result form a single trace"""
    score_str = f'{score:.2f}'
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

    sep = separator or ' '

    print(
        f'{trace_id}{sep}'
        f'{trace_start.isoformat(timespec="milliseconds")}{sep}'
        f'{trace_end.isoformat(timespec="milliseconds")}{sep}'
        f'{score_str}{sep if outlier_str else ""}'
        f'{outlier_str}',
        file=file
    )


def is_threshold_set(threshold):
    return 0 < threshold < 1


def download(url, timeout=None):
    """obspy creates Temporary files when supplying URLs for miniSEED
    (same for inventories?). So let's handle this here
    """
    with request.urlopen(request.Request(url), timeout=timeout or 30) as resp:
        bio = BytesIO()
        while True:
            chunk = resp.read(1024)
            if not chunk:
                break
            bio.write(chunk)
        bio.seek(0)
        return bio


def read_metadata(path_or_url, download_timeout=None):
    """wrapper around obspy read_inventory because the latter creates a temporary
    file if the input is a remote url
    """
    if is_remote_url(path_or_url):
        path_or_url = download(path_or_url, download_timeout)  # -> BytesIO
    return read_inventory(path_or_url, format="STATIONXML")


def read_data(path_or_url, format='MSEED', headonly=False, download_timeout=None,
              **kwargs): # noqa
    """wrapper around obspy read because the latter creates a temporary
    file if the input is a remote url
    """
    if is_remote_url(path_or_url):
        path_or_url = download(path_or_url, download_timeout)  # -> BytesIO
    return read(path_or_url, format=format, headonly=headonly, **kwargs)


class StreamIterator:
    """Class for iterating over given data and metadata arguments, either
    given as files / directory or URLs
    """
    def __init__(self):
        # metadata url or path mapped to a list of waveform url(s) or path(s):
        self._data = defaultdict(list)
        # ObSpy response cache:
        self._metadata_cache = {}

    def add_url(self, url, metadata_path, waveform_length, download_count):
        """Add a new FDSN URL, either station or dataselect. In the former
        case, the last three parameters control what segment waveform to
        download, and how
        """
        station_url, dataselect_url = fdsn.get_station_and_dataselect_urls(url)

        if url == dataselect_url:
            if not metadata_path:
                params = {p: v for p, v in fdsn.querydict(url).items()
                          if p in fdsn.DEFAULT_PARAMS}
                params['level'] = 'response'
                metadata_path = fdsn.build_url(station_url, **params)
            self._data[metadata_path].append(url)
            return

        if metadata_path:
            raise ValueError('Conflict: with a station url '
                             'you cannot also provide the "metadata" '
                             'argument')
        params = fdsn.querydict(url)
        params['level'] = 'response'
        params.pop('format', None)
        metadata_path = fdsn.build_url(station_url, **params)

        for dataselect_url in fdsn.get_dataselect_urls(url):
            params = fdsn.querydict(dataselect_url)
            start = datetime.fromisoformat(params['start'])
            end = datetime.fromisoformat(params['end'])
            total_seconds = (end - start).total_seconds()
            wlen = timedelta(seconds=float(waveform_length))
            max_download_count = int(total_seconds / wlen.total_seconds())
            if max_download_count < 1:
                raise ValueError(f'Total download period (~={int(total_seconds)}s) < '
                                 f'download window ({wlen.total_seconds()}s)')
            max_download_count = min(max_download_count, download_count)
            for _ in range(max_download_count):
                params['start'] = start.replace(microsecond=0).isoformat()
                params['end'] = (start+wlen).replace(microsecond=0).isoformat()
                url = fdsn.build_url(dataselect_url,  **params)
                self._data[metadata_path].append(url)
                start += timedelta(seconds=total_seconds/max_download_count)

    def add_dir(self, path, metadata_path=None):
        """Add a new directory, populated with miniSEED (*.mseed) files

        :param path: path to a direcotry (str)
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
        self.add_files(filepaths, metadata_path)

    def add_files(self, filepaths, metadata_path):
        """Add miniSEED files with relative metadata path (StationXML)"""
        if not filepaths:
            raise FileNotFoundError('No miniseed file provided')
        if not metadata_path:
            raise FileNotFoundError('No metadata (Station XML) file provided')
        if not isfile(metadata_path):
            raise ValueError('No metadata (Station XML) file: %s' %
                             metadata_path)
        for fpath in filepaths:
            self._data[metadata_path].append(fpath)

    def process(self, sort_by_time=False,
                aggregate: str or None = None,
                progressbar_output: TextIO or None = sys.stderr,
                info_output: TextIO or None = None,
                download_timeout: int or None = None):
        """Processes all added files/URLs and return the results"""
        if aggregate:
            aggregates = ('min', 'max', 'median', 'mean')
            if aggregate not in aggregates:
                raise ValueError(f'"aggregate" not in {str(aggregates)}')

        rows = []
        if not self._data:
            return rows

        # compute pbar step: for any StationXMl/metadata, count 1 (the station download)
        # + all associated waveforms (also to be downloaded):
        pbar_step = 1.0/sum(len(waveforms)+1 for waveforms in self._data.values())
        pbar_val = 0
        # load model now: it takes ~=1 second and is usually lazy loaded,
        # but this means that the progressbar would show misleading results
        # at the beginning
        load_default_trained_model()
        streams = defaultdict(list)
        with ProgressBar(progressbar_output) as pbar:
            for metadata_path, waveform_paths in self._data.items():  # paths or urls
                pbar_val += pbar_step
                pbar.set_progress(pbar_val)
                if metadata_path not in self._metadata_cache:
                    try:
                        self._metadata_cache[metadata_path] = \
                            read_metadata(metadata_path,
                                          download_timeout=download_timeout)
                    except Exception as exc:
                        if info_output:
                            print(f'Metadata error, {str(exc)}. {metadata_path}',
                                  file=info_output)
                        continue

                traces = []
                for path in waveform_paths:
                    pbar_val += pbar_step
                    pbar.set_progress(pbar_val)
                    try:
                        for t in read_data(path, download_timeout=download_timeout):
                            traces.append(t)
                    except Exception as exc:
                        if info_output:
                            print(f'Waveform error, {str(exc)}. {path}',
                                  file=info_output)
                if not traces:
                    continue

                scores = traces_scores(traces, self._metadata_cache[metadata_path])
                for trace, score in zip(traces, scores):
                    streams[trace.get_id()].append({
                        'id': trace.get_id(),
                        'start': trace.stats.starttime.datetime,
                        'end': trace.stats.endtime.datetime,
                        'score': score
                    })

        if not aggregate:
            for values in streams.values():
                rows.extend(sorted(values, key=lambda value: value['start']))
        else:
            for uid, values in streams.items():
                scores_ = [value['score'] for value in values]
                val = np.nan
                if not np.isnan(scores_).all():
                    if aggregate == 'mean':
                        val = np.nanmean(scores_)
                    elif aggregate == 'min':
                        val = np.nanmin(scores_)
                    elif aggregate == 'max':
                        val = np.nanmax(scores_)
                    else:
                        val = np.nanmedian(scores_)
                rows.append({
                    'id': uid,
                    'start': min(value['start'] for value in values),
                    'end': max(value['end'] for value in values),
                    aggregate: val
                })

            if sort_by_time:
                rows = sorted(rows, key=lambda _: _['start'])

        if not rows and info_output:
            print('No data to analyze found', file=info_output)
        return rows


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

    with warnings.catch_warnings(record=False) as wrn:  # noqa
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
