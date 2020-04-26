# -*- coding: utf-8 -*-

import asyncio
from collections import deque
from typing import List

import aiomisc
from loguru import logger

from .settings import Settings


class Batcher:
    """ Batcher enqueues a series of events from the receiver to
        bulk submit into Elasticsearch.
    """

    queue: deque
    _lock: asyncio.Lock

    def __init__(self, queue_max_size: int):
        self.queue = deque(maxlen=queue_max_size)
        self._lock = asyncio.Lock()

    async def insert(self, event: dict):
        """ Inserts a single event into the queue.
        """

        async with self._lock:
            self.queue.append(event)

    async def get_batch(self, batch_size: int) -> List[dict]:
        """ Returns a batch of events up to `batch_size`.
            If there are not `batch_size` elements in the deque,
            all remaining elements will be returned from the deque.
        """

        batch_size = min(batch_size, len(self.queue))

        async with self._lock:
            return [self.queue.popleft() for _ in range(batch_size)]

    async def is_empty(self) -> bool:
        """ Returns whether or not the batcher is empty.
            Useful for waiting to stop the application.
        """

        async with self._lock:
            return len(self.queue) > 0

    async def remaining(self) -> int:
        """ Returns the number of events in the queue
        """

        async with self._lock:
            return len(self.queue)


class BatcherService(aiomisc.Service):

    queue_max_size: int = 200

    async def start(self):
        """ Registers the batcher instance into the application context.
        """

        batcher = Batcher(
            queue_max_size=self.queue_max_size,
        )

        self.context["batcher"] = batcher