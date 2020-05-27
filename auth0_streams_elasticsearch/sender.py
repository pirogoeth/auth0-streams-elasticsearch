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

    send_after_events: int
    send_after_time: int
    send_loop_wait: float = 0.1
    tasks: List[asyncio.Task] = []
    _stop: asyncio.Event = asyncio.Event()

    __required__ = frozenset([
        "send_after_events",
        "send_after_time",
    ])

    async def start(self):
        """ The main loop of the sending service
        """

        logger.info("Sender started!")

        batcher: Batcher = await self.context["batcher"]
        begin = None
        while not self._stop.is_set():
            # During this loop, we need to keep track of time.
            # Each iteration, we will need to do a few things:
            # - If the timer is None and the batcher has items, start the timer.
            # - Check if there's a current batch that's larger than `self.send_after_events`
            #   - If greater, get the batch, send, and update begin time.
            # - Check if the current time is greater than `begin + self.send_after_time`
            #   - If greater, get a batch > 0 from the batcher, send, and update begin time.
            # - Poll the results of all pending send tasks.
            # - Sleep for a short amount of time and continue.
            events = None
            if not (await batcher.is_empty()):
                # Non-empty batcher triggers the timer
                if begin is None:
                    begin = time.monotonic()
                    await asyncio.sleep(self.send_loop_wait)
                    continue

                if (items := await batcher.remaining()) > self.send_after_events:
                    logger.debug(f"Fetching batch due to {items} queue > {self.send_after_events} threshold")
                    events = await batcher.get_batch(self.send_after_events)
                elif (now := time.monotonic()) > (begin + self.send_after_time):
                    logger.debug(f"Fetching batch due to time trigger ({now} > {begin} + {self.send_after_time})")
                    events = await batcher.get_batch(self.send_after_events)
                else:
                    logger.debug("Wait for threshold")
                    await asyncio.sleep(self.send_loop_wait)
                    continue

                # Ship the events and restart the timer
                begin = None
                logger.debug(f"Starting task to ship {len(events)} events")
                self.tasks.append(self.loop.create_task(self.send(events)))

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
            await asyncio.sleep(1)

    async def poll_sending_tasks(self):
        """ Poll all tasks attached to this sender instance and update
            the list of tasks as they are finished.
        """

        next_tasks = []
        for task in self.tasks:
            task_log = logger.bind(task=task)
            try:
                result = task.result()
                task_log.bind(result=result).debug(f"Completed successfully")
            except asyncio.InvalidStateError:
                task_log.debug("Still running")
                next_tasks.append(task)
            except Exception as err:
                task_log.bind(error=err).error(f"Completed unsuccessfully with errors")

        self.tasks = next_tasks

    async def send(self, batch: List[dict]) -> dict:
        """ Given a batch of events, bulk-submits them to Elasticsearch
            via the client.
        """

        client = await self.context["client"]

        # This is the bulk API response from Elasticsearch
        response = await client.send(batch)

        # Check for errors
        if response["errors"]:
            raise BulkSendingError(response)

        return response


class BulkSendingError(Exception):
    """ Raised when Elasticsearch returns an error or errors 
        for a bulk insertion
    """

    def __init__(self, response: dict):
        self.errors = response["items"]

    def __repr__(self):
        description = ""
        for item in self.errors:
            item_id = item["index"]["_id"]
            index = item["index"]
            if not index.get("error"):
                continue

            error_type = index["error"]["type"]
            error_reason = index["error"]["reason"]
            description += f"\tError processing bulk item {item_id}: {error_type}\n\t\t{error_reason}\n\n"

        return description

    __str__ = __repr__