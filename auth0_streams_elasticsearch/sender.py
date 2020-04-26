# -*- coding: utf-8 -*-

import asyncio
import time
from datetime import timedelta
from typing import List

import aiomisc
from loguru import logger

from .batcher import Batcher
from .client import Client
from .settings import Settings


class SenderService(aiomisc.Service):

    client: Client
    send_after_events: int
    send_after_time: int
    send_loop_wait: float
    tasks: List[asyncio.Task] = []
    _stop: asyncio.Event = asyncio.Event()

    __required__ = frozenset([
        "client",
        "send_after_events",
        "send_after_time",
        "send_loop_wait",
    ])

    async def start(self):
        """ The main loop of the sending service
        """

        self.start_event.set()

        batcher: Batcher = await self.context["batcher"]
        begin = time.monotonic()
        while not self._stop.is_set():
            # During this loop, we need to keep track of time.
            # Each iteration, we will need to do a few things:
            # - Check if there's a current batch that's larger than `self.send_after_events`
            #   - If greater, get the batch, send, and update begin time.
            # - Check if the current time is greater than `begin + self.send_after_time`
            #   - If greater, get a batch > 0 from the batcher, send, and update begin time.
            # - Poll the results of all pending send tasks.
            # - Sleep for a short amount of time and continue.
            events = None
            if not (await batcher.is_empty()):
                if await batcher.remaining() > self.send_after_events:
                    events = await batcher.get_batch(self.send_after_events)
                elif time.monotonic() > (begin + self.send_after_time):
                    events = await batcher.get_batch(self.send_after_events)

                if events is not None:
                    begin = time.monotonic()
                    self.tasks.append(asyncio.create_task(self.send(events)))

            await self.poll_sending_tasks()
            await asyncio.sleep(self.send_loop_wait)

        self._stop.clear()
        logger.debug("Sender loop closing")

    async def stop(self):
        """ Stops the main loop of the sending service and waits for all
            pending tasks to complete.
        """

        self._stop.set()

        # Once the sending loop stops, we'll handle polling the tasks to completion.
        await self._stop.wait()

        while self.tasks:
            logger.info(f"Waiting for pending tasks to complete.. ({len(self.tasks)} remaining)")
            await self.poll_sending_tasks()

    async def poll_sending_tasks(self):
        """ Poll all tasks attached to this sender instance and update
            the list of tasks as they are finished.
        """

        next_tasks = []
        for task in self.tasks:
            task_log = logger.bind(task=task)
            try:
                result = await task.result()
                task_log.debug(f"Completed successfully with result {result}")
            except asyncio.InvalidStateError:
                task_log.debug("Still running")
                next_tasks.append(task)
            except Exception as err:
                task_log.error(f"Completed unsuccessfully with error {err}")

        self.tasks = next_tasks

    async def send(self, batch: List[dict]):
        """ Given a batch of events, bulk-submits them to Elasticsearch
            via the client.
        """

        # This is the bulk API response from Elasticsearch
        response = await self.client.send(batch)

        # Check for errors
        if response["errors"]:
            logger.bind(response=response).error("Elasticsearch encountered errors ingesting events")

        return response