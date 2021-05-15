# -*- coding: utf-8 -*-

# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html

import base64
from w3lib.html import get_base_url
from .items import CrawlItem
from scrapy import Spider
import json
from .extractors import MicroformatExtractor


class SearchboxPipeline(object):
    def process_item(self, item: CrawlItem, spider: Spider):
        url = item['url']

        if 'html' in item:
            try:
                html = item['html']
                base_url = get_base_url(html, url)
                extractor = MicroformatExtractor(base_url, html)
                try:
                    tags = sorted(set(extractor.get_tags()))
                    item['article_tags'] = tags
                except Exception as e:
                    spider.logger.exception(str(e))

                date_published = extractor.get_published_date()
                if date_published is not None:
                    item['article_published_date'] = date_published.isoformat()
            except Exception as e:
                spider.logger.exception(str(e))

        return item


class CleanupPipeline(object):
    def process_item(self, item: CrawlItem, spider: Spider):
        if 'html' in item:
            del item['html']

        return item
