# -*- coding: utf-8 -*-

import asyncio
import os
import sys

import aiohttp
import aiomisc
from loguru import logger

from . import (
    batcher, client, logprop,
    receiver, sender, settings,
)


def cleanup_runner(runner: aiohttp.web.BaseRunner):
    async def cleanup(*args, **kw):
        await runner.cleanup()

    return cleanup


def start():
    aiomisc.new_event_loop()

    logprop.install()

    logger.remove()
    logger.add(sys.stdout, serialize=True)

    s = settings.Settings()
    c = client.init(s)

    services = [
        batcher.BatcherService(
            queue_max_size=s.QUEUE_MAX_SIZE,
        ),
        receiver.ReceiverService(
            address=s.BIND_ADDRESS,
            bearer_token=s.BEARER_TOKEN,
            port=s.BIND_PORT,
        ),
        sender.SenderService(
            client=c,
            send_after_time=s.SEND_AFTER_TIME,
            send_after_n_events=s.SEND_AFTER_N_EVENTS,
            send_loop_wait=s.SEND_LOOP_WAIT,
        ),
    ]
    with aiomisc.entrypoint(*services) as loop:
        loop.run_forever()