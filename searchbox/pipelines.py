# -*- coding: utf-8 -*-

# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html

from w3lib.html import get_base_url
from .items import CrawlItem
from scrapy import Spider
from .extractors import MicroformatExtractor


class SearchboxPipeline(object):
    def process_item(self, item: CrawlItem, spider: Spider) -> CrawlItem:
        url = item['url']

        if 'html' in item:
            try:
                html = item.get('html')
                if not html:
                    html = '<html></html>'
                base_url = get_base_url(html, url)
                # TODO: Fix 2021-05-15 12:55:25 [pocket] ERROR: to_unicode must receive a bytes, str or unicode object, got NoneType
                # Traceback (most recent call last):
                #   File "/home/d/code/projects/searchbox/searchbox/pipelines.py", line 23, in process_item
                #     base_url = get_base_url(html, url)
                #   File "/home/d/code/projects/searchbox/venv/lib/python3.9/site-packages/w3lib/html.py", line 284, in get_base_url
                #     text = to_unicode(text, encoding)
                #   File "/home/d/code/projects/searchbox/venv/lib/python3.9/site-packages/w3lib/util.py", line 23, in to_unicode
                #     raise TypeError('to_unicode must receive a bytes, str or unicode '
                # TypeError: to_unicode must receive a bytes, str or unicode object, got NoneType

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
    def process_item(self, item: CrawlItem, _spider: Spider) -> CrawlItem:
        if 'html' in item:
            del item['html']

        return item
