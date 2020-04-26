# -*- coding: utf-8 -*-

from typing import Iterator, List

import aioelasticsearch
from loguru import logger

from .settings import Settings


class Client:
    """ Elasticsearch client for ingesting bulk data
    """

    def __init__(self, settings: Settings):

        auth = None
        if settings.ELASTICSEARCH_USERNAME:
            auth = (settings.ELASTICSEARCH_USERNAME, settings.ELASTICSEARCH_PASSWORD)

        es_config = {
            "hosts": settings.ELASTICSEARCH_HOSTS.split(","),
            "verify_certs": settings.ELASTICSEARCH_SSL_VERIFY,
        }

        if auth:
            es_config.update({"http_auth": auth})

        self.es = aioelasticsearch.Elasticsearch(**es_config)
        self.index_name = settings.ELASTICSEARCH_INDEX_NAME

    async def send(self, events: List[dict]):

        return await self.es.bulk(
            self.iterate_docs(events),
            index=self.index_name,
            _source=False,
        )

    def iterate_docs(self, events: List[dict]) -> Iterator[dict]:

        for event in events:
            yield {"update": {
                "_index": self.index_name,
                "_id": event["log_id"]
            }}

            yield event


def init(settings: Settings):

    return Client(settings)