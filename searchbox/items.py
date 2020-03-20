# -*- coding: utf-8 -*-

import scrapy


class CrawlItem(scrapy.Item):
    name = scrapy.Field()
    description = scrapy.Field()
    url = scrapy.Field()
    last_update = scrapy.Field()
    content = scrapy.Field()
    github_backlink = scrapy.Field()
    alt_url = scrapy.Field()
    pocket_tags = scrapy.Field()
