from instagram.client import InstagramAPI
from instagram.bind import InstagramAPIError

class InstagramAPICycler(object):
    def __init__(self, tokens):
        self._tokens = tokens
        self._apis = {}
        for i, one_token in enumerate(tokens):
            api_obj = InstagramAPI(access_token=one_token)
            self._apis[i] = {
                "api_object": api_obj,
                "token": one_token,
                "usage_count": 0
            }
        self._pos = 0

    @property
    def api(self):
        the_api = self._apis[self._pos]
        the_api["usage_count"] += 1
        self._pos = (self._pos + 1) % len(self._tokens)
        return the_api.get('api_object')

    def __str__(self):
        return 'InstagramAPICycler() %d tokens' % len(self._tokens)


def get_all_paginated_data(api_obj, func_str, *args, **kwargs):
    try:
        func = getattr(api_obj, func_str)
    except (AttributeError, TypeError) as e:
        raise InstagramAPIError('%s is not a valid InstagramAPI method' % func_str)

    result = []
    try:
        partial, next_ = func(*args, **kwargs)
        if partial:
            result.extend(partial)
    except InstagramAPIError as e:
        print e
        return result

    while next_:
        partial, next_ = func(with_next_url=next_)
        if partial:
            result.extend(partial)

    return result
