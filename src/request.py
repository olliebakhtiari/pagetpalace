# Python standard.
import math
import time

# Third-party.
import requests

# Local.
from tools.logger import *


class RequestMixin:
    def __init__(self, access_token, default_headers, default_params, url):
        self.access_token = access_token
        self.default_headers = default_headers
        self.default_params = default_params
        self.url = url

    @classmethod
    def retry_if_5xx_or_429(cls,
                            response: requests.Response,
                            func: str,
                            retry_count: int,
                            retry_wait_time: float,
                            **kwargs) -> requests.Response:
        if retry_count >= 4:
            return response
        if response.status_code >= 500 or response.status_code == 429:
            logger.error(f'Failed request - {response.status_code}, {response.text}. Retrying...', exc_info=True)
            time.sleep(retry_wait_time)
            return getattr(cls, func)(**kwargs)

    def _request(self,
                 endpoint: str = '',
                 method: str = 'GET',
                 headers=None,
                 params=None,
                 data=None,
                 retry_count: int = 0,
                 retry_wait_time: float = 0.5) -> dict:
        if headers is None:
            headers = self.default_headers
        if params is None:
            params = self.default_params
        if data is None:
            data = {}
        response = requests.request(
            method=method,
            url=f'{self.url}/{endpoint}',
            headers=headers,
            params=params,
            data=data,
        )
        self.retry_if_5xx_or_429(
            response,
            func='_request',
            endpoint=endpoint,
            method=method,
            headers=headers,
            params=params,
            data=data,
            retry_count=retry_count + 1,
            retry_wait_time=min(math.exp(retry_wait_time), 5),
        )

        return response.json()
