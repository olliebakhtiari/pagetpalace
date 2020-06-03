# Third-party.
import requests
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_result,
    after_log,
)

# Local.
from tools.logger import *


def check_5xx_or_429_status_code(response: requests.Response) -> bool:
    return response.status_code >= 500 or response.status_code == 429


class RequestMixin:
    def __init__(self, access_token, default_headers, default_params, url):
        self.access_token = access_token
        self.default_headers = default_headers
        self.default_params = default_params
        self.url = url

    @retry(
        retry=retry_if_result(check_5xx_or_429_status_code),
        stop=stop_after_attempt(3),
        after=after_log(logger, logging.ERROR),
        wait=wait_exponential(max=5),
        reraise=True
    )
    def retry_if_5xx_or_429(self,
                            method: str,
                            endpoint: str,
                            headers: dict,
                            params: dict,
                            data: dict,) -> requests.Response:
        return requests.request(
            method=method,
            url=f'{self.url}/{endpoint}',
            headers=headers,
            params=params,
            data=data,
        )

    def _request(self,
                 endpoint: str = '',
                 method: str = 'GET',
                 headers=None,
                 params=None,
                 data=None) -> dict:
        if headers is None:
            headers = self.default_headers
        if params is None:
            params = self.default_params
        if data is None:
            data = {}
        response = self.retry_if_5xx_or_429(method=method, endpoint=endpoint, headers=headers, params=params, data=data)

        return response.json()
