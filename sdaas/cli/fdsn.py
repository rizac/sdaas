"""
Fdsn utilities for parsing url passed in the command line and fetching data

Created on 10 Sep 2020

@author: Riccardo Z. <rizac@gfz-potsdam.de>
"""

import re
from urllib import parse, request
from datetime import datetime


def get_station_and_dataselect_urls(url):
    """Return the tuple (station_url, dataselect_url). Raise ValueError
    if `url` is not valid station ort dataselect FDSN URL
    """
    fdsn_re = '[a-zA-Z_]+://.+?/fdsnws/(?:station|dataselect)/\\d/query?.*'
    if not re.match(fdsn_re, url):
        raise ValueError(f'Invalid FDSN URL: {url}')
    # urlsplit is a namedtuple (scheme, netloc, path, query, fragment). Convert to list
    # as we need to modify its path (element at index 2):
    parts = list(parse.urlsplit(url))
    urls = [url, url]  # station, dataselect
    if '/dataselect/' in parts[2]:
        parts[2] = parts[2].replace('/dataselect/', '/station/')
        urls[0] = parse.urlunsplit(parts)
    elif '/station/' in parts[2]:
        parts[2] = parts[2].replace('/station/', '/dataselect/')
        urls[1] = parse.urlunsplit(parts)
    else:
        raise ValueError(f'Invalid FDSN URL: {url}')
    return tuple(urls)


# default FDSN parameters used in this module (to avoid confusion with multiple names):
DEFAULT_PARAMS = {
    "net": ("net", "network"),
    "sta": ("sta", "station"),
    "loc": ("loc", "location"),
    "cha": ("cha", "channel"),
    "start": ('start', 'starttime'),
    "end": ('end', 'endtime')
}


def querydict(url, check_dates=True):
    """Return the query string of `url` in form of a dict.
    Raises ValueError if some parameter is missing or invalid

    :param url: a URL
    :param check_dates: check the validity of start and end params (if given)
    """
    url_parts = parse.urlsplit(url)
    # object above is a named tuple:
    # (scheme, netloc, path, query, fragment)
    try:
        ret = {}
        # populate dict and check no multiple argument given:
        for param, values in parse.parse_qs(url_parts.query).items():
            if len(values) > 1:
                raise ValueError(f'Multiple values for "{param}"')
            ret[param] = values[0]

        # check default arguments:
        for def_param, params in DEFAULT_PARAMS.items():
            tmp_ret = {p: ret[p] for p in params if p in ret}
            if len(tmp_ret) > 1:
                raise ValueError(f'Multiple values for "{"/".join(params)}"')
            elif len(tmp_ret) == 1 and next(iter(tmp_ret)) != def_param:
                ret[def_param] = ret.pop(next(iter(tmp_ret)))

        if check_dates:
            for param in ('start', 'end'):
                if param in ret:
                    try:
                        # check datetime (just a check, keep str as value)
                        datetime.fromisoformat(ret[param])
                    except (ValueError, TypeError):
                        raise ValueError(f'Invalid date-time for "{param}"')
            if 'start' in ret:
                end = ret.get('end', datetime.utcnow().isoformat())
                if datetime.fromisoformat(ret['start']) >= datetime.fromisoformat(end):
                    raise ValueError('Invalid date-time range: decrease start '
                                     'or increase end (if provided)')

    except (KeyError, ValueError) as exc:
        raise ValueError(f'{str(exc)}. URL: {url}')

    return ret


def get_dataselect_urls(url, timeout=None):
    """Get all dataselect URLs from the given FDSN station url

    :param url: a FDSN station query URL. If dataselect, then `[url]` is returned

    :return: a list of dataselect urls. Each url will have at least the parameters
        'net', 'sta', 'start' and 'end'
    """
    fdsn_station_url, fdsn_dataselect_url = get_station_and_dataselect_urls(url)
    if url == fdsn_dataselect_url:
        return [url]
    params = querydict(url)
    params['level'] = 'station'
    params['format'] = 'text'
    req = request.Request(build_url(url, **params))
    with request.urlopen(req, timeout=timeout) as response:
        the_page = response.read().strip().decode('utf-8')
    urls = []
    if not the_page:
        return urls
    now = datetime.utcnow().isoformat()
    for line in the_page.split('\n'):
        if '#' in line:
            continue
        cells = [_.strip() for _ in line.split('|')]
        args = {
            **{p: v for p, v in params.items() if p in DEFAULT_PARAMS},
            'net': cells[0],
            'sta': cells[1]
        }
        args.setdefault('start', cells[-2])
        args.setdefault('end', cells[-1] or now)
        urls.append(build_url(fdsn_dataselect_url, **args))
    return urls


def build_url(url, **queryparams):
    """Build a new URL by replacing or adding the query string assembled from
    `queryargs`l

    :param: queryparams: a `dict` of param and values representing the new
        query string in the URL. Values not string will be converted to string
        (except datetimes, converted to their ISO format string)

    :return a string denoting the url build from the given queryparams
    """
    url_parts = list(parse.urlsplit(url))
    # object above is a named tuple:
    # (scheme, netloc, path, query, fragment)
    url_parts[3] =[]
    for k, v in queryparams.items():
        if isinstance(v, datetime):
            v = v.isoformat()
        url_parts[3].append(f'{k}={v}')
    url_parts[3] = '&'.join(url_parts[3])
    return parse.urlunsplit(url_parts)
