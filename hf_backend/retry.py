from __future__ import annotations
import time
from requests.exceptions import ConnectionError, Timeout
from urllib3.exceptions import ProtocolError


RETRYABLE_EXCEPTIONS = (ConnectionError, Timeout, ProtocolError, OSError)


def with_retry(fn, *args, retries: int = 3, delay: float = 1.0, **kwargs):
    last_err = None
    for attempt in range(retries):
        try:
            return fn(*args, **kwargs)
        except RETRYABLE_EXCEPTIONS as e:
            last_err = e
            if attempt < retries - 1:
                time.sleep(delay * (attempt + 1))
    raise last_err
