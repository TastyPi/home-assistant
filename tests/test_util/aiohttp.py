"""Aiohttp test utils."""
import asyncio
from contextlib import contextmanager
import functools
import json as _json
from unittest import mock
from urllib.parse import urlparse, parse_qs
import yarl


class AiohttpClientMocker:
    """Mock Aiohttp client requests."""

    def __init__(self):
        """Initialize the request mocker."""
        self._mocks = []
        self.mock_calls = []

    def request(self, method, url, *,
                auth=None,
                status=200,
                text=None,
                data=None,
                content=None,
                json=None,
                params=None,
                headers=None,
                exc=None):
        """Mock a request."""
        if json:
            text = _json.dumps(json)
        if text:
            content = text.encode('utf-8')
        if content is None:
            content = b''
        if params:
            url = str(yarl.URL(url).with_query(params))

        self.exc = exc

        self._mocks.append(AiohttpClientMockResponse(
            method, url, status, content))

    def get(self, *args, **kwargs):
        """Register a mock get request."""
        self.request('get', *args, **kwargs)

    def put(self, *args, **kwargs):
        """Register a mock put request."""
        self.request('put', *args, **kwargs)

    def post(self, *args, **kwargs):
        """Register a mock post request."""
        self.request('post', *args, **kwargs)

    def delete(self, *args, **kwargs):
        """Register a mock delete request."""
        self.request('delete', *args, **kwargs)

    def options(self, *args, **kwargs):
        """Register a mock options request."""
        self.request('options', *args, **kwargs)

    @property
    def call_count(self):
        """Number of requests made."""
        return len(self.mock_calls)

    @asyncio.coroutine
    def match_request(self, method, url, *, data=None, auth=None, params=None,
                      headers=None):  # pylint: disable=unused-variable
        """Match a request against pre-registered requests."""
        for response in self._mocks:
            if response.match_request(method, url, params):
                self.mock_calls.append((method, url, data))

                if self.exc:
                    raise self.exc
                return response

        assert False, "No mock registered for {} {} {}".format(method.upper(),
                                                               url, params)


class AiohttpClientMockResponse:
    """Mock Aiohttp client response."""

    def __init__(self, method, url, status, response):
        """Initialize a fake response."""
        self.method = method
        self._url = url
        self._url_parts = (None if hasattr(url, 'search')
                           else urlparse(url.lower()))
        self.status = status
        self.response = response

    def match_request(self, method, url, params=None):
        """Test if response answers request."""
        if method.lower() != self.method.lower():
            return False

        if params:
            url = str(yarl.URL(url).with_query(params))

        # regular expression matching
        if self._url_parts is None:
            return self._url.search(url) is not None

        req = urlparse(url.lower())

        if self._url_parts.scheme and req.scheme != self._url_parts.scheme:
            return False
        if self._url_parts.netloc and req.netloc != self._url_parts.netloc:
            return False
        if (req.path or '/') != (self._url_parts.path or '/'):
            return False

        # Ensure all query components in matcher are present in the request
        request_qs = parse_qs(req.query)
        matcher_qs = parse_qs(self._url_parts.query)
        for key, vals in matcher_qs.items():
            for val in vals:
                try:
                    request_qs.get(key, []).remove(val)
                except ValueError:
                    return False

        return True

    @asyncio.coroutine
    def read(self):
        """Return mock response."""
        return self.response

    @asyncio.coroutine
    def text(self, encoding='utf-8'):
        """Return mock response as a string."""
        return self.response.decode(encoding)

    @asyncio.coroutine
    def release(self):
        """Mock release."""
        pass


@contextmanager
def mock_aiohttp_client():
    """Context manager to mock aiohttp client."""
    mocker = AiohttpClientMocker()

    with mock.patch('aiohttp.ClientSession') as mock_session:
        instance = mock_session()

        for method in ('get', 'post', 'put', 'options', 'delete'):
            setattr(instance, method,
                    functools.partial(mocker.match_request, method))

        yield mocker
