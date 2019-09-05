import time
import asyncio
import pandas as pd
import datetime
import numpy as np
import math

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
