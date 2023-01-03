# -*- coding: utf-8 -*-
import json
import re
from datetime import datetime
from typing import Any, Dict, Generator, Optional, Union
from urllib.parse import urlencode

import scrapy
from scrapy.core.engine import Response
from scrapy.http import Request

from ..extractors import body_text, is_processable
from ..items import CrawlItem
from ..secrets_loader import SECRETS

RESULTS_PER_REQUEST = 50


class PocketSpider(scrapy.Spider):  # type: ignore
    name = 'pocket'

    consumer_key = SECRETS.pocket['consumer_key']
    access_token = SECRETS.pocket['access_token']

    def start_requests(self) -> Generator[Request, None, None]:
        yield self.make_pocket_request()

    def parse_webpage(self, response: Response) -> Generator[CrawlItem, None, None]:
        if not is_processable(response):
            return
        url = response.meta['url']
        # Ignore title, we get it from the pocket API
        _, content, html = body_text(response)
        yield CrawlItem(url=url, content=content, html=html)

    def parse_pocket_page(self, response: Response) -> Generator[Union[CrawlItem, Request], None, None]:
        if not is_processable(response):
            return
        result = json.loads(response.text)
        if result['status'] != 1:
            return

        items = result['list']
        for key in sorted(items.keys()):
            item = items[key]
            
            name = item.get('resolved_title') or item.get('given_title')
            description = item.get('excerpt')
            last_update = datetime.fromtimestamp(int(item['time_added'])).isoformat()

            url = item.get('resolved_url')
            alt_url = item['given_url']

            if not url:
                url = alt_url

            if alt_url == url:
                alt_url = None
                
            if 'tags' in item:
                tags = [' '.join(re.split('_|-', item)) for item in list(item['tags'].keys())]
            else:
                tags = None

            yield CrawlItem(name=name, description=description, last_update=last_update, url=url, alt_url=alt_url, pocket_tags=tags)
            req = scrapy.Request(url=url, callback=self.parse_webpage)
            # Save original URL, in case of redirects, since it's the key of the item
            req.meta['url'] = url
            yield req
            
        if len(items) > 0:
            yield self.make_pocket_request(response)

    def make_pocket_request(self, previous_page: Optional[Response] = None) -> Request:
        offset = 0 if previous_page is None else previous_page.meta['next_offset']
        
        post_data = {'consumer_key': PocketSpider.consumer_key,
                     'access_token': PocketSpider.access_token,
                     'count': RESULTS_PER_REQUEST,
                     'offset': offset,
                     'state': 'all',
                     'detailType': 'complete'}

        url = 'https://getpocket.com/v3/get'

        headers = {'Content-Type': 'application/x-www-form-urlencoded'}

        req = Request(url=url, method='POST', callback=self.parse_pocket_page,
                      body=encode_post_data(post_data), headers=headers)
        req.meta['next_offset'] = offset + RESULTS_PER_REQUEST
        # The pocket API is not crawlable, but we're not really crawling
        req.meta['dont_obey_robotstxt'] = True
        return req


def encode_post_data(data: Dict[str, Any]) -> str:
    result = []
    for k, v in data.items():
        result.append((str(k), str(v)))

    return urlencode(result, doseq=True)
