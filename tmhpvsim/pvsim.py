import asyncio
import csv
import click
import os
import json
import datetime
import numpy as np
import aio_pika
from collections import namedtuple

import logging
logger = logging.getLogger(__name__)

from .utils import fixedclock, SynchronizingFunnel
from .pvmodel import PVModel

# Definition of the fundamental namedtuple which is synced per time-stamp
# in the SynchronizingFunnel and then passed through its out-ward queue
Data = namedtuple("Data", ['meter', 'pv'], defaults=[np.nan, np.nan])

async def read_pv_values(funnel, realtime):
    """Feeds a fixed rate stream of simulated pv values to `funnel`

    Parameters
    ----------
    funnel : SynchronizingFunnel

    realtime : bool
        If false, fixedclock does not wait to sync up with realtime

    See also
    --------
    SynchronizingFunnel

    """

    pvmodel = PVModel()

    async for time in fixedclock(rate=1, realtime=realtime):
        time_sec = datetime.datetime(*time.timetuple()[:6])
        await funnel.put(time_sec, pv=pvmodel.next(time_sec))

async def read_amqp(funnel, url, exchange, loop):
    """Connect to AMQP and receive meter values to put into `meter_queue`

    """
    connection = await aio_pika.connect_robust(url, loop=loop)
    logger.info("Connection established")

    async with connection:
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=1)
        logger.info("Channel opened")

        meter_exchange = await channel.declare_exchange(
            exchange,
            aio_pika.ExchangeType.FANOUT
        )
        logger.info(f"'{exchange}' exchange declared.")

        queue = await channel.declare_queue(exclusive=True)
        await queue.bind(meter_exchange)

        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    meter_value = json.loads(message.body.decode())
                    time = datetime.datetime(*message.timestamp[:6])
                    await funnel.put(time, meter=meter_value)

async def write_file_from_queue(filename, queue):
    """Receives Data tuples from `queue` and writes them to `filename` as CSV

    Adds timestamp and computed residual load.

    """
    with open(filename, mode='w', newline='', buffering=1) as file:
        writer = csv.writer(file)
        writer.writerow(['time'] + list(Data._fields) + ['residual load'])
        while True:
            time, data = await queue.get()
            writer.writerow([time] + list(data) + [data.meter - data.pv])

@click.command()
@click.argument('file')
@click.option('--amqp-url', default=os.environ.get("AMQP_URL"),
              help="AMQP URL (defaults to 'amqp://localhost:5672/')")
@click.option('--exchange', default=os.environ.get("TMHPVSIM_EXCHANGE", 'meter'),
              help="The name of the exchange (defaults to 'meter')")
@click.option('-v', '--verbose', count=True,
              help="Increase logging level from default WARN")
@click.option('--realtime/--no-realtime', default=True,
              help="Switch off rate limiting (for simulation)")
def pvsim(file, amqp_url, exchange, verbose, realtime):
     # -v -> INFO, -vv -> DEBUG
    logging.basicConfig(level=logging.WARN - 10 * verbose)

    loop = asyncio.get_event_loop()

    data_queue = asyncio.Queue(loop=loop)
    funnel = SynchronizingFunnel(Data, data_queue)

    loop.create_task(read_pv_values(funnel, realtime))
    loop.create_task(read_amqp(funnel, amqp_url, exchange, loop))
    loop.create_task(write_file_from_queue(file, data_queue))

    try:
        loop.run_forever()
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        if len(funnel._cache) > 0:
            logger.warn(f"{len(funnel._cache)} undelivered meter_values have been lost")
            logger.debug(funnel._cache)
