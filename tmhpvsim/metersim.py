import click
import os
import asyncio
import json
from aio_pika import connect_robust, Message, DeliveryMode, ExchangeType
import numpy as np

import logging
logger = logging.getLogger(__name__)

from .utils import fixedclock

async def send_queue_to_amqp(meter_queue, url, exchange, loop):
    """
    Connect to AMQP and continuously sent meter values from `meter_queue`


    """
    connection = await connect_robust(url, loop=loop)
    logger.info("Connection established")

    async with connection:
        channel = await connection.channel()
        logger.info("Channel opened")

        meter_exchange = await channel.declare_exchange(
            exchange,
            ExchangeType.FANOUT
        )
        logger.info(f"'{exchange}' exchange declared.")

        logger.info("Starting sending of random meter values...")

        while True:
            time, meter = await meter_queue.get()

            logger.debug(f"Sending meter value {meter}")
            # unsure, whether sending meter timestamp as message timestamp violates the protocol?
            message = Message(
                timestamp=time,
                body=json.dumps(meter, ensure_ascii=False).encode(),
                content_type='application/json'
            )
            await meter_exchange.publish(message, routing_key="")

            meter_queue.task_done()

def get_meter_value():
    """Sample a single meter value from a uniform random distribution [0, 9000]"""
    return 9000 * np.random.random()

async def read_meter_values(meter_queue, realtime):
    """Read one meter value per second and put it into `meter_queue`

    See also
    --------
    get_meter_value
    """
    async for time in fixedclock(rate=1, realtime=realtime):
        meter = get_meter_value()
        await meter_queue.put((time, meter))

@click.command()
@click.option('--amqp-url', default=os.environ.get("AMQP_URL"),
              help="AMQP URL (defaults to 'amqp://localhost:5672/')")
@click.option('--exchange', default=os.environ.get("TMHPVSIM_EXCHANGE", 'meter'),
              help="The name of the exchange (defaults to 'meter')")
@click.option('-v', '--verbose', count=True)
@click.option('--realtime/--no-realtime', default=True,
              help="Switch off rate limiting (for simulation)")
def metersim(amqp_url, exchange, verbose, realtime):
     # -v -> INFO, -vv -> DEBUG
    logging.basicConfig(level=logging.WARN - 10 * verbose)

    loop = asyncio.get_event_loop()
    meter_queue = asyncio.Queue(loop=loop)
    loop.create_task(read_meter_values(meter_queue, realtime))
    loop.create_task(send_queue_to_amqp(meter_queue, amqp_url, exchange, loop))
    try:
        loop.run_forever()
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        if not meter_queue.empty():
            logger.warn(f"{meter_queue.qsize()} undelivered meter_values have been lost")
