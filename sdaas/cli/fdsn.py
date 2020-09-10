'''
Fdsn utilities for parsing url passed in the command line and fetching data

Created on 10 Sep 2020

@author: riccardo
'''

from urllib import parse
from datetime import datetime


fdsn_re = '[a-zA-Z_]+://.+?/fdsnws/(?:station|dataselect)/\\d/query?.*'


def get_querydict(url):
    '''
    Returns the query string of `url` in form of a dict, with parameter
    names (str) mapped to their value (list). An additional 'URL' key
    is added to the dict, with the query string removed, so that the
    full url can be reconstructed with :func:`get_dataselect_url` or
    :func:`get_station_url`

    Raises if the url does not contain at least the parameters 'net' 'sta'
        'start' (or alternatively 'network', 'station', 'starttime')
    '''
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
            'net': get_query_entry(queryargs, "net", "network")[1],
            'sta': get_query_entry(queryargs, "sta", "station")[1],
            'start': get_query_entry_dtime(queryargs, 'start', 'starttime')[1]
        }
        # optional arguments
        for params in [("loc", "location"), ("cha", "channel")]:
            try:
                ret[params[0]] = get_query_entry(queryargs, *params)[1]
            except KeyError:
                pass
        # in case of end,if missing, set now as endtime:
        try:
            ret['end'] = get_query_entry_dtime(queryargs, 'end', 'endtime')[1]
        except KeyError:
            ret['end'] = datetime.utcnow().replace(microsecond=0)
        # little check:
        if ret['start'] >= ret['end']:
            raise ValueError(f'Invalid "start" >= "end": {url}')
    except (KeyError, ValueError) as exc:
        raise ValueError(f'{str(exc)}. URL: {url}')
    # add base URL:
    ret['URL'] = (f'{url_splitted.scheme}://{url_splitted.netloc}'
                  f'{url_splitted.path}')
    return ret


def get_dataselect_url(querydict, start=None, end=None):
    '''
    Converts the given `querydict` to the relative dataselect url
    for downloading data in the command line interface

    :param: querydict: a `dict` as returned from :func:`get_querydict`
    :param start: (datetime.datetime or None) if provided and not None,
        replaces the url start time with this value
    :param start: (datetime.datetime or None) if provided and not None,
        replaces the url end time with this value

    :return: a string denoting a valid FDSN dataselect url
    '''
    return get_url(querydict, start, end).\
        replace('/station/', '/dataselect/')


def get_station_metadata_url(querydict, start=None, end=None):
    '''
    Converts the given `querydict` to the relative station url
    for downloading metadata in the command line interface. The parameter
    'level' in the returned url will be set to 'response'

    :param: querydict: a `dict` as returned from :func:`get_querydict`
    :param start: (datetime.datetime or None) if provided and not None,
        replaces the url start time with this value
    :param start: (datetime.datetime or None) if provided and not None,
        replaces the url end time with this value

    :return: a string denoting a valid FDSN dataselect url
    '''
    return get_url(querydict, start, end, level='response').\
        replace('/dataselect/', '/station/')


def get_url(querydict, start=None, end=None, **additional_args):
    '''
    Converts the given `querydict` to the relative url

    :param: querydict: a `dict` as returned from :func:`get_querydict`
    :param start: (datetime.datetime or None) if provided and not None,
        replaces the url start time with this value
    :param start: (datetime.datetime or None) if provided and not None,
        replaces the url end time with this value
    :param additional_args: additional arguments which will override
        any given argument, if present. Values will be converted with the
        `str` function when encoded in the url

    :return a string denoting the url build from the given querydict
    '''
    args = dict(querydict)
    args['start'] = (start or args['start']).isoformat()
    args['end'] = (end or args['end']).isoformat()
    args = {**args, **additional_args}
    url = args.pop('URL') + '?'
    for key, val in args.items():
        url += f'&{str(key)}={str(val)}'
    return url


def get_query_entry_dtime(query_dict, *keys):
    '''
    Same as :func:`get_query_entry` but converts the parameter value to
    date time (raises if not parsable)

    :see: :func:`get_query_entry`

    :return: the tuple (param, value) (value is a datetime object)
    '''
    par, val = get_query_entry(query_dict, *keys)
    try:
        return par, datetime.fromisoformat(val)
    except Exception:
        raise ValueError(f'Invalid date-time in "{par}"')


def get_query_entry(query_dict, *keys):
    '''
    Returns the tuple (param, value) from the given `query_dict`.
    'param' is the parameter name found (searched in the provided `key`(s))
    and `value` is the parameter value.

    Raises if zero or more than one key is provided, if the given provided key
    is typed more than once

    :param: querydict: a `dict` as returned from :func:`get_querydict`
    :param keys: the parameter names (or keys) to be searched for in the query
        dict

    :return: the tuple (param, value)
    '''
    params = [k for k in keys if k in query_dict]
    if len(params) > 1:
        raise ValueError(f'Conflicting parameters "{"/".join(params)}"')
    elif len(params) == 0:
        raise KeyError(f'Missing parameter(s) "{"/".join(keys)}" ')
    param = params[0]
    val = query_dict[param]
    if len(val) > 1:
        raise ValueError(f'Invalid multiple values for "{param}"')
    return param, val[0]
