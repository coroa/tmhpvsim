import time
import asyncio
import pandas as pd
import datetime
import numpy as np
import math
import signal
from functools import wraps

import logging
logger = logging.getLogger(__name__)

async def fixedclock(rate=1, realtime=True):
    """Asynchronuous generator yielding timestamps at a fixed `rate`

    Parameters
    ----------
    rate : float
        Number of timestamps per second
    realtime : bool, optional
        If unset, only sleeps minimal amounts of time (10msec)

    Yields
    ------
    now : datetime.datetime

    Note
    ----
    Requires Python 3.6.
    """
    start_time = time.time()
    iteration = 0

    while True:
        clock_time = start_time + iteration / rate
        delay = clock_time - time.time() if realtime else 1e-2
        if delay > 0:
            logger.debug(f"Iteration {iteration}: Sleeping for {delay} seconds ..")
            await asyncio.sleep(delay)
        elif delay < -10:
            logger.warn("We are {delay} seconds behind realtime")

        yield datetime.datetime.fromtimestamp(clock_time)

        iteration += 1

class SynchronizingFunnel:
    """
    """

    def __init__(self, typ, outqueue):
        self._cache = {}
        self._typ = typ
        self._outqueue = outqueue

    async def put(self, key, **updates):
        if key in self._cache:
            data = self._cache.pop(key)._replace(**updates)
        else:
            data = self._typ(**updates)

        logger.debug(f"{key}, {data}")

        if not np.isnan(data).any():
            await self._outqueue.put((key, data))
        else:
            self._cache[key] = data

propagate = forever = ...

def asyncretry(
    func=None,
    *,
    attempts=3,
    delay=5,
    fallback=propagate,
    retry_exceptions=(Exception,),
    fatal_exceptions=(asyncio.CancelledError,),
):
    """Decorator for catching retry_exceptions and restarting evaluation

    Arguments
    ---------
    attempts : int|forever
        Number of attempts or `forever`
    delay : float
        Number of seconds to wait between attempts
    fallback : propagate|Exception
        Either re-raise (propagate) or raise another Exception
    retry_exceptions : Sequence[Exception]
        Exceptions which should be re-tried
    fatal_exceptions : Sequence[Exception]
        Exception which should propagate through

    Usage
    -----
    @asyncretry(attempts=3, delay=5)
    async def some_func(a):
        raise Exception("Test")

    will propagate the Exception after 3 attempts, each time waiting 5s before
    attempting again.

    Note
    ----
    Arguments of the wrapped function should be immutable
    """
    def wrapper(func):
        @wraps(func)
        async def wrapped(*func_args, **func_kwargs):
            attempt = 1

            while True:
                try:
                    return await func(*func_args, **func_kwargs)
                except fatal_exceptions:
                    raise
                except retry_exceptions as exc:
                    context = {
                        'func': func,
                        'attempt': attempt,
                        'attempts': "infinity" if attempts is forever else attempts,
                    }

                    if attempt == attempts:
                        logger.warning(
                            exc.__class__.__name__ + ' -> Attempts (%(attempt)d) are over for %(func)r',  # noqa
                            context,
                            exc_info=exc,
                        )
                        if fallback is propagate:
                            raise

                        if isinstance(Exception) or issubclass(fallback, Exception):
                            raise fallback from exc

                        if callable(fallback):
                            ret = await fallback(func_args, func_kwargs, loop=loop)
                        else:
                            ret = fallback

                        return ret

                    logger.debug(
                        exc.__class__.__name__ + ' -> Tried attempt #%(attempt)d from total %(attempts)s for %(func)r',  # noqa
                        context,
                        exc_info=exc,
                    )

                    await asyncio.sleep(delay)
                    attempt += 1

        return wrapped

    if func is None:
        return wrapper

    if callable(func):
        return wrapper(func)

    raise NotImplementedError

async def cancel_on_sigint(coroutine):
    loop = asyncio.get_event_loop()
    try:
        main_task = loop.create_task(coroutine)
        loop.add_signal_handler(signal.SIGINT, main_task.cancel)
        return await main_task
    except asyncio.CancelledError as exc:
        logger.info("Cancelled, shutting down", exc_info=exc)
    finally:
        loop.remove_signal_handler(signal.SIGINT)

def asyncrun(coroutine, *, debug=False):
    """Run coroutine in main event loop and cancel on SIGINT

    See also
    --------
    asyncio.run is the original, but does not handle SIGINT
    """

    loop = asyncio.events.get_event_loop()
    main_task = loop.create_task(coroutine)
    try:
        loop.add_signal_handler(signal.SIGINT, main_task.cancel)
        loop.set_debug(debug)
        return loop.run_until_complete(main_task)
    except asyncio.CancelledError as exc:
        logger.info("Cancelled, shutting down", exc_info=exc)
    finally:
        loop.remove_signal_handler(signal.SIGINT)

        # We might want to cancel all remaining tasks and maybe log any
        # exceptions, similar to asyncio.runners._cancel_all_tasks, but since
        # we re-use the main event_loop we might cancel away stuff which does
        # not belong to us!
        loop.run_until_complete(loop.shutdown_asyncgens())
