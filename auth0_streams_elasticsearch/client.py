# -*- coding: utf-8 -*-

import asyncio
from typing import Iterator, List

import aioelasticsearch
import aiomisc
from loguru import logger

from .log import make_propagating_logger
from .settings import Settings


class Client:
    """ Elasticsearch client for ingesting bulk data
    """

    def __init__(self, username: str, password: str, hosts: str, index_name: str, ssl_verify: bool, *, loop: asyncio.AbstractEventLoop):

        auth = None
        if username and password:
            auth = (username, password)

        es_config = {
            "hosts": hosts.split(","),
            "verify_certs": ssl_verify,
        }

        if auth:
            es_config.update({"http_auth": auth})

        self.es = aioelasticsearch.Elasticsearch(loop=loop, **es_config)
        self.index_name = index_name 

    async def send(self, events: List[dict]):

        return await self.es.bulk(
            self.iterate_docs(events),
            index=self.index_name,
            _source=False,
        )

    def iterate_docs(self, events: List[dict]) -> Iterator[dict]:

        for event in events:
            yield {"index": {
                "_index": self.index_name,
                "_id": event["log_id"]
            }}

            yield event["data"]


class ClientService(aiomisc.Service):

    __required__ = frozenset([
        "username",
        "password",
        "hosts",
        "index_name",
        "ssl_verify",
    ])

    username: str
    password: str
    hosts: str
    index_name: str
    ssl_verify: bool

    async def start(self):
        """ Registers the client instance into the application context.
        """

        client = Client(
            self.username,
            self.password,
            self.hosts,
            self.index_name,
            self.ssl_verify,
            loop=self.loop,
        )

        self.context["client"] = client