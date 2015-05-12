import time
from datetime import timedelta
from datetime import datetime
from itertools import chain

from instagram.client import InstagramAPI
from instagram.bind import InstagramAPIError


class InstagramAPIHandler(object):
    API_SLEEP_TIME = timedelta(hours=1)

    def __init__(self, token, index):
        self._api_obj = InstagramAPI(access_token=token)
        self._token = token
        self._index = index
        self._uses = 0
        self._sleep_until = None

    @property
    def api(self):
        self._uses += 1
        return self._api_obj

    @property
    def token(self):
        return self._token

    @property
    def index(self):
        return self._index

    @property
    def usage_count(self):
        return self._uses

    def is_available(self):
        if self._sleep_until is not None and self._sleep_until < datetime.utcnow():
            self._sleep_until = None
        return self._sleep_until is None

    def sleep(self):
        self._sleep_until = datetime.utcnow() + InstagramAPIHandler.API_SLEEP_TIME
        print 'Sleeping this API until %s' % self._sleep_until

    def __str__(self):
        return 'InstagramAPIHandler(token=%s, index=%d, uses=%d)' % (self._token, self._index, self._uses)


class InstagramAPICycler(object):
    CYCLE_WAIT_SECONDS = 60

    def __init__(self, tokens):
        self._tokens = tokens
        self._apis = []
        for i, one_token in enumerate(tokens):
            self._apis.append(InstagramAPIHandler(one_token, i))
        self._active_api = None
        self._active_index = None
        self._next_index = 0

    def _one_api_cycle(self):
        return chain(
            self._apis[ self._next_index : len(self._apis) ],
            self._apis[ 0 : self._next_index ]
        )

    def _next_active_api(self):
        for api_handler in self._one_api_cycle():
            self._set_active_api(api_handler)
            if api_handler.is_available():
                return api_handler.api
            else:
                continue

        # No API objects were available
        time.sleep(InstagramAPICycler.CYCLE_WAIT_SECONDS)
        return self._next_active_api()

    @property
    def api(self):
        return self._next_active_api()

    def _set_active_api(self, api):
        self._active_api = api
        self._active_index = self._active_api.index
        self._next_index = (self._next_index + 1) % len(self._tokens)

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

        while next_:
            partial, next_ = func(with_next_url=next_)
            if partial:
                result.extend(partial)

    except InstagramAPIError as e:
        if e.status_code == 429:
            print 'SLEEPING API: %s' % e
            api_obj.sleep()

    return result


def instagram_media_to_dict(media_obj):
    media_dict = {}
    [
        media_dict.setdefault(attr, getattr(media_obj, attr)) for
        attr in dir(media_obj) if not attr.startswith('__') and
        not callable(getattr(media_obj, attr))
    ]
    return media_dict