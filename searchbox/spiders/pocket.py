# -*- coding: utf-8 -*-
import scrapy
from scrapy.http import Request
from urllib.parse import urlencode
import json
from datetime import datetime

from ..secrets_loader import SECRETS
from ..items import CrawlItem
from ..extractors import body_text, is_processable
from typing import Dict
import re

RESULTS_PER_REQUEST = 50


class PocketSpider(scrapy.Spider):
    name = 'pocket'

    consumer_key = SECRETS.pocket['consumer_key']
    access_token = SECRETS.pocket['access_token']

    def start_requests(self):
        urls = ['https://getpocket.com/v3/get']
        for url in urls:
            yield self.make_pocket_request()

    def parse_webpage(self, response):
        if not is_processable(response):
            return
        url = response.meta['url']
        content = body_text(response)
        yield CrawlItem(url=url, content=content)

    def parse_pocket_page(self, response):
        if not is_processable(response):
            return
        result = json.loads(response.body_as_unicode())
        if result['status'] != 1:
            return

        items = result['list']
        for key in sorted(items.keys()):
            item = items[key]
            
            name = item['resolved_title']
            description = item['excerpt']
            last_update = datetime.fromtimestamp(int(item['time_added'])).isoformat()

            url = item['resolved_url']
            alt_url = item['given_url']
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

    def make_pocket_request(self, previous_page=None):
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


def encode_post_data(data: Dict[str, any]):
    result = []
    for k, v in data.items():
        result.append((str(k), str(v)))

    return urlencode(result, doseq=True)
