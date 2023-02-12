# -*- coding: utf-8 -*-

from typing import Generator, Union
from scrapy.http import Request
from . import items


SpiderRequests = Generator[Request, None, None]
SpiderItems = Generator[items.CrawlItem, None, None]
SpiderResults = Generator[Union[items.CrawlItem, Request], None, None]
