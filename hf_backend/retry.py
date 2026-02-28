from __future__ import annotations
import time

from httpx import ConnectError, TimeoutException, NetworkError, ProtocolError
from huggingface_hub.utils import HfHubHTTPError


_TRANSPORT_ERRORS = (ConnectError, TimeoutException, NetworkError, ProtocolError)


def _is_retryable(err: Exception) -> bool:
    if isinstance(err, _TRANSPORT_ERRORS):
        return True
    if isinstance(err, HfHubHTTPError):
        resp = getattr(err, "response", None)
        if resp is not None and resp.status_code >= 500:
            return True
    return False


def with_retry(fn, *args, retries: int = 3, delay: float = 1.0, **kwargs):
    last_err = None
    for attempt in range(retries):
        try:
            return fn(*args, **kwargs)
        except (HfHubHTTPError, *_TRANSPORT_ERRORS) as e:
            if not _is_retryable(e):
                raise
            last_err = e
            if attempt < retries - 1:
                time.sleep(delay * (attempt + 1))
    raise last_err
