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
from .log_types import LOG_TYPES
from .settings import Settings


class ReceiverService(AIOHTTPService):
    """ Wrapper around AIOHTTPSERVER to add our own `aiohttp.web.Application`
    """

    __required__ = frozenset(["bearer_token"])

    bearer_token: str

    async def create_application(self) -> web.Application:

        app = web.Application()
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
                task = asyncio.create_task(self.process_events(events))
                task.add_done_callback(self.on_process_done)

                return web.json_response(
                    {"message": "Received!"},
                    dumps=ujson.dumps,
                )
            except TypeError:
                return web.HTTPUnprocessableEntity(reason="Expected JSON body")
        else:
            return web.HTTPBadRequest()

    async def process_events(self, events: List[dict]):
        """ Takes a list of events, transforms them, and inserts them into
            the batcher queue.
        """

        batcher: Batcher = await self.context["batcher"]

        events = map(self.transform_event, events.get("logs", []))
        coros = map(batcher.insert, events)
        return await asyncio.gather(coros)

    def transform_event(self, event: dict) -> dict:
        """ Adds the long-form description of the type identifier,
            along with any other transforms that should happen
        """

        data = event["data"]
        data["type_description"] = LOG_TYPES.get(
            data["type"], {}
        ).get("event", "Unknown event type")

        return event

    def on_process_done(self, fut: asyncio.Future):
        """ Logs the result of the process events task.
        """

        logger.info(f"Event process task complete: {fut.result()}")