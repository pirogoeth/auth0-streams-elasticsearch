# -*- coding: utf-8 -*-

import functools
from hmac import compare_digest
from typing import Callable

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
            web.post("/api/ingest", self.handler),
        ])

        return app

    async def handler(self, request: web.Request) -> web.Response:
        batcher: Batcher = await self.context["batcher"]

        auth = request.headers.get("authorization")
        if not auth or not compare_digest(f"Bearer {self.bearer_token}", auth):
            return web.HTTPForbidden()

        if request.body_exists and request.can_read_body:
            try:
                event = await request.json(loads=ujson.loads)
                await batcher.insert(self.transform_event(event))

                return web.json_response(
                    {"message": "Received!"},
                    dumps=ujson.dumps,
                )
            except TypeError:
                return web.HTTPUnprocessableEntity(reason="Expected JSON body")
        else:
            return web.HTTPBadRequest()

    def transform_event(self, event: dict) -> dict:
        data = event["data"]
        data["type_description"] = LOG_TYPES.get(
            data["type"], {}
        ).get("event", "Unknown event type")

        return event