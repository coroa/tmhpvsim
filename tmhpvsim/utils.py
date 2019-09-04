import time
import asyncio
import pandas as pd
import datetime

import logging
logger = logging.getLogger(__name__)

async def fixedclock(rate=1):
    """Asynchronuous generator yielding timestamps at a fixed `rate`

    Parameters
    ----------
    rate : float
        Number of timestamps per second

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
        delay = clock_time - time.time()
        if delay > 0:
            logger.debug(f"Iteration {iteration}: Sleeping for {delay} seconds ..")
            await asyncio.sleep(delay)
            logger.debug(f"Iteration {iteration}: Slept for {delay} seconds. (Hopefully)")
        elif delay < -10:
            logger.warn("We are {delay} seconds behind realtime")

        yield datetime.datetime.fromtimestamp(clock_time)

        iteration += 1
