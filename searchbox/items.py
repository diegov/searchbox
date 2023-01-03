# -*- coding: utf-8 -*-

from typing import List, Optional, Set
from dataclasses import dataclass, field


@dataclass
class CrawlItem:
    name: Optional[str] = field(default=None)
    description: Optional[str] = field(default=None)
    url: Optional[str] = field(default=None)
    last_update: Optional[str] = field(default=None)
    content: Optional[str] = field(default=None)
    repository_backlink: Optional[str] = field(default=None)
    twitter_backlink: Optional[str] = field(default=None)
    alt_url: Optional[str] = field(default=None)
    repository_tags: List[str] = field(default_factory=list)
    pocket_tags: List[str] = field(default_factory=list)
    twitter_tags: List[str] = field(default_factory=list)
    article_tags: List[str] = field(default_factory=list)
    article_published_date: Optional[str] = field(default=None)
    html: Optional[str] = field(default=None)

    def get_all_tags(self) -> List[str]:
        all_tags: Set[str] = set()
        all_tags.update(self.twitter_tags)
        all_tags.update(self.article_tags)
        all_tags.update(self.pocket_tags)
        return sorted(all_tags)
