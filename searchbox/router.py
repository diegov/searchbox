from typing import Callable, List, Tuple
from scrapy import Spider
from scrapy.http import Request

from .types import SpiderRequests


class Router(object):
    def __init__(self) -> None:
        self.matchers: List[Tuple[Spider, Callable[[Request], SpiderRequests]]] = []

    @staticmethod
    def _merge_metadata(target: Request, existing: Request) -> Request:
        for k in existing.meta.keys():
            if k not in target.meta:
                target.meta[k] = existing.meta[k]
        return target

    def process_request(self, spider: Spider, r: Request) -> SpiderRequests:
        for s, matcher in self.matchers:
            if s == spider:
                continue

            replaced = False

            for new_req in matcher(r):
                replaced = True
                s.logger.info(
                    "Taking over URL %s from %s. New URL: %s",
                    r.url,
                    spider.name,
                    new_req.url,
                )
                yield Router._merge_metadata(new_req, r)

            if replaced:
                return

        yield r
