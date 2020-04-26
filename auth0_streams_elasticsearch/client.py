# -*- coding: utf-8 -*-

from typing import Iterator, List

import aioelasticsearch
from loguru import logger

from .settings import Settings


class Client:
    """ Elasticsearch client for ingesting bulk data
    """

    def __init__(self, settings: Settings):
        self.es = aioelasticsearch.Elasticsearch(
            hosts=settings.ELASTICSEARCH_HOSTS.split(","),
            verify_certs=settings.ELASTICSEARCH_SSL_VERIFY,
            http_auth=(settings.ELASTICSEARCH_USERNAME, settings.ELASTICSEARCH_PASSWORD),
        )
        self.index_name = settings.ELASTICSEARCH_INDEX_NAME

    async def send(self, events: List[dict]):

        await self.es.bulk()


    def iterate_docs(self, events: List[dict]) -> Iterator[dict]:

        for event in events:
            yield {"update": {
                "_index": self.index_name,
                "_id": event["log_id"]
            }}

            yield event


def init(settings: Settings):
    return Client(settings)