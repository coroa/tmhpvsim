import click
import os
import asyncio
import json
from aio_pika import connect, Message, DeliveryMode, ExchangeType
import numpy as np

import logging
logger = logging.getLogger(__name__)

from .utils import fixedclock, asyncretry, forever, asyncrun

@asyncretry(delay=5, attempts=forever)
async def send_queue_to_amqp(meter_queue, url, exchange):
    """
    Connect to AMQP and continuously sent meter values from `meter_queue`
    """
    connection = await connect(url)
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
            await asyncio.shield(
                meter_exchange.publish(message, routing_key="")
            )

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

async def _metersim(amqp_url, exchange, realtime):
    meter_queue = asyncio.Queue()
    gathered_tasks = asyncio.gather(
        read_meter_values(meter_queue, realtime),
        send_queue_to_amqp(meter_queue, amqp_url, exchange)
    )

    try:
        await gathered_tasks
    finally:
        gathered_tasks.cancel()

        if not meter_queue.empty():
            logger.warn(f"{meter_queue.qsize()} undelivered meter_values have been lost")

@click.command()
@click.option('--amqp-url', default=os.environ.get("AMQP_URL"),
              help="AMQP URL (defaults to 'amqp://localhost:5672/')")
@click.option('--exchange', default=os.environ.get("TMHPVSIM_EXCHANGE", 'meter'),
              help="The name of the exchange (defaults to 'meter')")
@click.option('-v', '--verbose', count=True,
              help="Increase logging level from default WARN")
@click.option('--realtime/--no-realtime', default=True,
              help="Switch off rate limiting (for simulation)")
def metersim(amqp_url, exchange, verbose, realtime):
    """
    Entrypoint for metersim application
    """
     # -v -> INFO, -vv -> DEBUG
    logging.basicConfig(level=logging.WARN - 10 * verbose)

    return asyncrun(_metersim(amqp_url, exchange, realtime))
