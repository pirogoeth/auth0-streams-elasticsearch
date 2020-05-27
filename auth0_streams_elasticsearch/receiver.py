# -*- coding: utf-8 -*-

import asyncio
import functools
from hmac import compare_digest
from typing import Callable, List

import ujson
from aiohttp import web
from aiomisc.service.aiohttp import AIOHTTPService
from loguru import logger

from .batcher import Batcher
from .log import make_propagating_logger
from .settings import Settings
from .types import LOG_TYPES


class ReceiverService(AIOHTTPService):
    """ Wrapper around AIOHTTPSERVER to add our own `aiohttp.web.Application`
    """

    __required__ = frozenset(["bearer_token"])

    bearer_token: str

    async def create_application(self) -> web.Application:

        app = web.Application(logger=make_propagating_logger("aiohttp.access"))
        app.add_routes([
            web.post("/", self.handler),
        ])

        return app

    async def handler(self, request: web.Request) -> web.Response:

        auth = request.headers.get("authorization")
        if not auth or not compare_digest(f"Bearer {self.bearer_token}", auth):
            return web.HTTPForbidden()

        if request.body_exists and request.can_read_body:
            try:
                events = await request.json(loads=ujson.loads)
                task = self.loop.create_task(self.queue_events(events))
                task.add_done_callback(self.on_queue_done)

                return web.json_response(
                    {"message": "Received!"},
                    dumps=ujson.dumps,
                )
            except TypeError:
                return web.HTTPUnprocessableEntity(reason="Expected JSON body")
        else:
            return web.HTTPBadRequest()

    async def queue_events(self, events: List[dict]):
        """ Takes a list of events, transforms them, and inserts them into
            the batcher queue.
        """

        batcher: Batcher = await self.context["batcher"]

        events = map(self.transform_event, events.get("logs", []))
        return await batcher.insert_many(events)

    def transform_event(self, event: dict) -> dict:
        """ Adds the long-form description of the type identifier,
            along with any other transforms that should happen
        """

        data = event["data"]
        data["type_description"] = LOG_TYPES.get(
            data["type"], {}
        ).get("event", "Unknown event type")

        return event

    def on_queue_done(self, fut: asyncio.Future):
        """ Logs the result of the process events task.
        """

        logger.info(f"Event queuing task completed: {fut.result()}")