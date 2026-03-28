"""
Retry + exponential backoff decorator.
Applied on every external call: Google Sheets, Vapi, WhatsApp, Telegram.
"""
import logging
from functools import wraps
from typing import Callable, Tuple, Type

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

logger = logging.getLogger(__name__)

# Default exception types that warrant a retry
DEFAULT_RETRYABLE = (Exception,)


def with_retry(
    max_attempts: int = 3,
    backoff_base: int = 2,
    retryable_exceptions: Tuple[Type[Exception], ...] = DEFAULT_RETRYABLE,
):
    """
    Decorator factory. Usage:

        @with_retry(max_attempts=3, backoff_base=2)
        def call_external_api(...):
            ...

    Waits 2^attempt seconds between retries (capped at 30s).
    """
    def decorator(func: Callable) -> Callable:
        @retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=backoff_base, min=1, max=30),
            retry=retry_if_exception_type(retryable_exceptions),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        )
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper
    return decorator
