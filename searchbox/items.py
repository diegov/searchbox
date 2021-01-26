# -*- coding: utf-8 -*-

import scrapy


class CrawlItem(scrapy.Item):
    name = scrapy.Field()
    description = scrapy.Field()
    url = scrapy.Field()
    last_update = scrapy.Field()
    content = scrapy.Field()
    github_backlink = scrapy.Field()
    twitter_backlink = scrapy.Field()
    alt_url = scrapy.Field()
    pocket_tags = scrapy.Field()
    twitter_tags = scrapy.Field()
    article_tags = scrapy.Field()
    article_published_date = scrapy.Field()
    html = scrapy.Field()

    def get_all_tags(self):
        all_tags = set()
        all_tags.update(self.get('twitter_tags') or [])
        all_tags.update(self.get('article_tags') or [])
        all_tags.update(self.get('pocket_tags') or [])
        return sorted(all_tags)
