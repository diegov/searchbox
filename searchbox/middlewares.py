# -*- coding: utf-8 -*-

# Define here the models for your spider middleware
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/spider-middleware.html

from collections.abc import Iterable
from typing import Any, Dict, Generator, Type, Union
from scrapy import Item, Request, Spider, signals
from scrapy.core.engine import Response
from scrapy.crawler import Crawler


class SearchboxSpiderMiddleware(object):
    # Not all methods need to be defined. If a method is not defined,
    # scrapy acts as if the spider middleware does not modify the
    # passed objects.

    @classmethod
    def from_crawler(
            cls: Type['SearchboxSpiderMiddleware'],
            crawler: Crawler
    ) -> 'SearchboxSpiderMiddleware':
        # This method is used by Scrapy to create your spiders.
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def process_spider_input(self, _response: Any, _spider: Any) -> None:
        # Called for each response that goes through the spider
        # middleware and into the spider.

        # Should return None or raise an exception.
        return None

    def process_spider_output(
            self,
            _response: Any,
            result: Iterable[Union[Request, Dict[str, Any], Item]],
            _spider: Any
    ) -> Generator[Union[Request, Dict[str, Any], Item], None, None]:
        # Called with the results returned from the Spider, after
        # it has processed the response.

        # Must return an iterable of Request, dict or Item objects.
        for i in result:
            yield i

    def process_spider_exception(self, _response: Any, _exception: Any, _spider: Any) -> None:
        # Called when a spider or process_spider_input() method
        # (from other spider middleware) raises an exception.

        # Should return either None or an iterable of Request, dict
        # or Item objects.
        pass

    def process_start_requests(self, start_requests: Iterable[Request], _spider: Any) -> Generator[Request, None, None]:
        # Called with the start requests of the spider, and works
        # similarly to the process_spider_output() method, except
        # that it doesn’t have a response associated.

        # Must return only requests (not items).
        for r in start_requests:
            yield r

    def spider_opened(self, spider: Spider) -> None:
        spider.logger.info('Spider opened: %s' % spider.name)


class SearchboxDownloaderMiddleware(object):
    # Not all methods need to be defined. If a method is not defined,
    # scrapy acts as if the downloader middleware does not modify the
    # passed objects.

    @classmethod
    def from_crawler(cls: Type['SearchboxDownloaderMiddleware'], crawler: Crawler) -> 'SearchboxDownloaderMiddleware':
        # This method is used by Scrapy to create your spiders.
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def process_request(self, _request: Any, _spider: Any) -> None:
        # Called for each request that goes through the downloader
        # middleware.

        # Must either:
        # - return None: continue processing this request
        # - or return a Response object
        # - or return a Request object
        # - or raise IgnoreRequest: process_exception() methods of
        #   installed downloader middleware will be called
        return None

    def process_response(self, _request: Any, response: Response, _spider: Any) -> Response:
        # Called with the response returned from the downloader.

        # Must either;
        # - return a Response object
        # - return a Request object
        # - or raise IgnoreRequest
        return response

    def process_exception(self, _request: Any, _exception: Any, _spider: Any) -> None:
        # Called when a download handler or a process_request()
        # (from other downloader middleware) raises an exception.

        # Must either:
        # - return None: continue processing this exception
        # - return a Response object: stops process_exception() chain
        # - return a Request object: stops process_exception() chain
        pass

    def spider_opened(self, spider: Spider) -> None:
        spider.logger.info('Spider opened: %s' % spider.name)
