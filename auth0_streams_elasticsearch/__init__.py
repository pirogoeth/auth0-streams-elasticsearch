# -*- coding: utf-8 -*-

import asyncio
import os

import aiohttp
import aiomisc
from loguru import logger

from . import (
    batcher, client, log,
    receiver, sender, settings,
)


def cleanup_runner(runner: aiohttp.web.BaseRunner):
    async def cleanup(*args, **kw):
        await runner.cleanup()

    return cleanup


def start():
    aiomisc.new_event_loop()

    s = settings.Settings()

    log.configure(s)

    services = [
        batcher.BatcherService(
            queue_max_size=s.QUEUE_MAX_SIZE,
        ),
        client.ClientService(
            username=s.ELASTICSEARCH_USERNAME,
            password=s.ELASTICSEARCH_PASSWORD,
            hosts=s.ELASTICSEARCH_HOSTS,
            index_name=s.ELASTICSEARCH_INDEX_NAME,
            ssl_verify=s.ELASTICSEARCH_SSL_VERIFY,
        ),
        receiver.ReceiverService(
            address=s.BIND_ADDRESS,
            bearer_token=s.BEARER_TOKEN,
            port=s.BIND_PORT,
        ),
        sender.SenderService(
            send_after_time=s.SEND_AFTER_TIME,
            send_after_events=s.SEND_AFTER_EVENTS,
        ),
    ]
    with aiomisc.entrypoint(*services) as loop:
        loop.run_forever()
