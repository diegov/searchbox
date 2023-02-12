# -*- coding: utf-8 -*-

from collections.abc import Iterable
from typing import Any, Callable, Type

from scrapy import Request, Spider, signals
from scrapy.crawler import Crawler

from .types import SpiderRequests, SpiderResults
from .router import Router


# It seems crawlers and spiders are 1 to 1 and the CrawlerProcess that unites
# everything is just a utility class to manage twisted's reactor, and is not
# reachable from here.
# Extensions are also 1 to 1 with crawlers.
# The Scrapy documentation doesn't explain the lifetimes and cardinalities of
# the different components, which would be important for the use cases I can
# think of of middleware and extensions.
# Hacking this in crawl.py also doesn't work, because Scrapy manages the
# python environment by itself and our modules are not available when the
# scraping script runs, so we can't actually load this or the router modules
# there.
# So I have no idea how to share a component among spiders, in a way that is
# idiomatic for Scrapy. Here we just hack it with a global variable.
# TODO: Check some Scrapy extension / middleware projects that might have a
# similar problem, to see how they handle this.
# Or just migrate to an UberSpider approach and bypass Scrapy's crawler / spider
# management.
_ROUTER = Router()


class URLRouterSpiderMiddleware(object):
    def __init__(self, router: Router) -> None:
        self.router = router

    @classmethod
    def from_crawler(
        cls: Type["URLRouterSpiderMiddleware"], crawler: Crawler
    ) -> "URLRouterSpiderMiddleware":        

        s = cls(_ROUTER)
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def process_spider_output(
        self,
        result: SpiderResults,
        spider: Spider,
        response: Any = None,
    ) -> SpiderResults:
        # TODO: Find a simpler method. The Request -> Iterator[Request]
        # process is not very clear, and forces spiders to construct a full request which
        # will be discarded, just to pass information to the router.
        # Spiders should return something _other_ than a request, a "RequestRouteRequest"?,
        # which the router would turn into requests based on the available spiders.
        # This process ideally would allow spiders to route requests to themselves.
        # Alternatively, the UberSpider could bypass all these problems

        for i in result:
            if isinstance(i, Request):
                yield from self.router.process_request(spider, i)
            else:
                yield i

    def process_start_requests(
        self, start_requests: Iterable[Request], spider: Spider
    ) -> SpiderRequests:
        for r in start_requests:
            yield from self.router.process_request(spider, r)

    def spider_opened(self, spider: Spider) -> None:
        # TOOD: I have no idea is we can be sure this will be executed for all crawlers,
        # before any of them start crawling. 
        if hasattr(spider, "get_url_matcher"):
            match_fn: Callable[[Request], SpiderRequests] = getattr(spider, 'get_url_matcher')()
            self.router.matchers.append((spider, match_fn))
