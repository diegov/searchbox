# -*- coding: utf-8 -*-

from typing import List, Set
import scrapy


class CrawlItem(scrapy.Item):  # type: ignore
    name = scrapy.Field()
    description = scrapy.Field()
    url = scrapy.Field()
    last_update = scrapy.Field()
    content = scrapy.Field()
    repository_backlink = scrapy.Field()
    twitter_backlink = scrapy.Field()
    alt_url = scrapy.Field()
    repository_tags = scrapy.Field()
    pocket_tags = scrapy.Field()
    twitter_tags = scrapy.Field()
    article_tags = scrapy.Field()
    article_published_date = scrapy.Field()
    html = scrapy.Field()

    def get_all_tags(self) -> List[str]:
        all_tags: Set[str] = set()
        all_tags.update(self.get('twitter_tags') or [])
        all_tags.update(self.get('article_tags') or [])
        all_tags.update(self.get('pocket_tags') or [])
        return sorted(all_tags)
