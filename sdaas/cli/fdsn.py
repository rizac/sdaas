"""
Fdsn utilities for parsing url passed in the command line and fetching data

Created on 10 Sep 2020

@author: Riccardo Z. <rizac@gfz-potsdam.de>
"""

import re
from urllib import parse, request
from datetime import datetime


# Backward compatibility with Python 3.6.9:
try:
    datetime.fromisoformat

    # Nothing raised, define datetime_fromisoformat as simple wrapper around
    # datetime.fromisoformat:
    def datetime_fromisoformat(iso_formatted_dtime):
        """Same as datetime.fromisoformat"""
        return datetime.fromisoformat(iso_formatted_dtime)

except AttributeError:  # Python 3.6.9:
    def datetime_fromisoformat(iso_formatted_dtime):
        """Return a datetime from the given ISO formatted string.
        For backward compatibility with Python<3.7
        """
        sep = 'T' if 'T' in iso_formatted_dtime else ' '
        for frmt in ["%Y-%m-%d{0}%H:%M:%S".format(sep),
                     "%Y-%m-%d{0}%H:%M:%S.%f".format(sep),
                     "%Y-%m-%d"]:
            # to make this method fully compatible with Py3.7, we should allow
            # either 3 or 6 digits after the seconds. Unfortunately, this was
            # not supported and we have only the "%f" option (1 to 6 digits)
            try:
                return datetime.strptime(iso_formatted_dtime, frmt)
            except Exception:
                pass
        raise ValueError("Invalid isoformat string: '%s'" % iso_formatted_dtime)


fdsn_re = '[a-zA-Z_]+://.+?/fdsnws/(?:station|dataselect)/\\d/query?.*'


def is_fdsn_dataselect_url(url):
    """Return True if `url` is a valid FDSN dataselect URL"""
    if not is_fdsn(url):
        raise ValueError('Invalid FDSN URL: %s' % url)
    return '/dataselect/' in url


def is_fdsn_station_url(url):
    """Return True if `url` is a valid FDSN station URL"""
    if not is_fdsn(url):
        raise ValueError('Invalid FDSN URL: %s' % url)
    return '/station/' in url


def is_fdsn(url):
    """Return True if `url` is a valid FDSN URL"""
    return re.match(fdsn_re, url)


def get_querydict(url):
    """Return the query string of `url` in form of a dict with keys
    'net' (mandatory), 'sta', 'cha' 'loc' 'start' 'end' (all optional)
    All dict values (query parameter values) are `str` (i.e., not casted).
    An additional 'URL' key is added to the dict, with the query string
    removed, so that the full url can be reconstructed with
    :func:`get_dataselect_url` or :func:`get_station_url`

    Raises if the url does not contain at least the parameters 'net' 'sta'
        'start' (or alternatively 'network', 'station', 'starttime')
    """
    url_splitted = parse.urlsplit(url)
    # object above is of the form:
    # ParseResult(scheme='http', netloc='www.example.org',
    #             path='/default.html', query='ct=32&op=92&item=98',
    #             fragment='')
    # now parse its query. Note that each element is a LIST!
    # (arguments might appear more times)
    queryargs = parse.parse_qs(url_splitted.query)
    try:
        # mandatory arguments:
        ret = {
            'net': _get_query_entry(queryargs, "net", "network")[1]
        }
        # optional arguments
        for params in [("loc", "location"), ("cha", "channel"),
                       ("sta", "station"), ('start', 'starttime'),
                       ('end', 'endtime')]:
            try:
                ret[params[0]] = _get_query_entry(queryargs, *params)[1]
                if params[0] in ('start', 'end'):
                    # check datetime (just a check, keep str as value)
                    try:
                        datetime_fromisoformat(ret[params[0]])
                    except Exception:
                        raise ValueError(f'Invalid date-time in "{params[0]}"')
            except KeyError:
                pass

        # little check:
        if 'start' in ret:
            now = datetime.utcnow().isoformat()
            if datetime_fromisoformat(ret['start']) >= \
                    datetime_fromisoformat(ret.get('end', now)):
                raise ValueError(f'Invalid time range, check (start, end) in {url}')
    except (KeyError, ValueError) as exc:
        raise ValueError(f'{str(exc)}. URL: {url}')
    # add base URL:
    ret['URL'] = (f'{url_splitted.scheme}://{url_splitted.netloc}'
                  f'{url_splitted.path}')
    return ret


def _get_query_entry(parse_qs_result, *keys):
    """Returns the tuple (param, value) from the given `parse_qs_result` (dict
    resulting from :func:`parse.parse_qs`.
    'param' is the parameter name found (searched in the provided `key`(s))
    and `value` is the parameter value.

    Raises if zero or more than one key is provided, if the given provided key
    is typed more than once

    :param: querydict: a `dict` as returned from :func:`get_querydict`
    :param keys: the parameter names (or keys) to be searched for in the query
        dict

    :return: the tuple (param, value)
    """
    params = [k for k in keys if k in parse_qs_result]
    if len(params) > 1:
        raise ValueError(f'Conflicting parameters "{"/".join(params)}"')
    elif len(params) == 0:
        raise KeyError(f'Missing parameter(s) "{"/".join(keys)}" ')
    param = params[0]
    val = parse_qs_result[param]
    if len(val) > 1:
        raise ValueError(f'Invalid multiple values for "{param}"')
    return param, val[0]


def get_dataselect_url(querydict, **queryargs):
    """Convert the given `querydict` to the relative dataselect url
    for downloading data in the command line interface

    :param: querydict: a `dict` as returned from :func:`get_querydict`
    :param queryargs: additional query arguments which will override
        any given argument, if present. Values will be converted with the
        `str` function when encoded in the url (for datetimes, isoformat
        will be used instead). None values means: remove the parameter

    :return: a string denoting a valid FDSN dataselect url
    """
    return get_url(querydict, **queryargs).\
        replace('/station/', '/dataselect/')


def get_station_url(querydict, **queryargs):
    """Convert the given `querydict` to the relative station url
    for downloading metadata in the command line interface. The parameter
    'level' in the returned url will be set to 'response'

    :param: querydict: a `dict` as returned from :func:`get_querydict`
    :param queryargs: additional query arguments which will override
        any given argument, if present (e.g., level='response' to download
        the station xml). Values will be converted with the
        `str` function when encoded in the url (for datetimes, isoformat
        will be used instead). None values means: remove the parameter

    :return: a string denoting a valid FDSN dataselect url
    """
    return get_url(querydict, **queryargs).\
        replace('/dataselect/', '/station/')


def get_station_urls(fdsn_query_url, timeout=None):
    """Get all station urls from the given fdsn_query_url

    :return: a list of station urls. Each url will have the query arguments
        net, sta, start and end
    """
    qdic = get_querydict(fdsn_query_url.replace('/dataselect/',
                                                '/station/'))
    url = get_url(qdic, level='station', format='text')
    req = request.Request(url)
    with request.urlopen(req, timeout=timeout) as response:
        the_page = response.read().strip().decode('utf-8')
    urls = []
    if not the_page:
        return urls
    now = datetime.utcnow().replace(microsecond=0).isoformat()
    for line in the_page.split('\n'):
        if '#' in line:
            continue
        cells = line.split('|')
        args = {
            'net': cells[0],
            'sta': cells[1],
            'start': qdic.get('start', cells[-2])
        }
        args['end'] = qdic.get('end', cells[-1].strip() or now)
        # remove args:
        args['level'] = None
        args['format'] = None
        urls.append(get_url(qdic, **args))
    return urls


def get_url(querydict, **queryargs):
    """Convert the given `querydict` to the relative url

    :param: querydict: a `dict` as returned from :func:`get_querydict`
    :param queryargs: additional query arguments which will override
        any given argument, if present. Values will be converted with the
        `str` function when encoded in the url (for datetimes, isoformat
        will be used instead). None values means: remove the parameter

    :return a string denoting the url build from the given querydict
    """
    args = dict(querydict)
    # args['start'] = (start or args['start']).isoformat()
    # args['end'] = (end or args['end']).isoformat()
    args = {**args, **queryargs}
    for key, val in queryargs.items():
        if val is None:
            args.pop(key)
    url = args.pop('URL') + '?'
    for key, val in args.items():
        url += f'&{str(key)}={_str(val)}'
    return url


def _str(paramvalue):
    try:
        return paramvalue.isoformat()
    except AttributeError:
        return str(paramvalue)
