import functools
import random
import sys
import time


def retry(timeout=300, interval=15, jitter=0.2, wait_on=Exception):
    """A decorator that allows to retry a section of code...
    ...until success or timeout.
    """

    def wrapper(function):
        @functools.wraps(function)
        def inner(*args, **kwargs):
            start = time.time()
            while True:
                try:
                    return function(*args, **kwargs)
                except wait_on as e:
                    skew = random.random() * jitter + (1 - jitter / 2)
                    print(
                        "Exception %r raised from %r.  Retry in %rs"
                        % (e, function, interval * skew),
                        file=sys.stderr,
                    )
                    time.sleep(interval * skew)
                    if (time.time() - start) >= timeout:
                        raise  # This re-raises the last exception.

        return inner

    return wrapper
