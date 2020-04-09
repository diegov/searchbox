#!/usr/bin/env python3

from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

settings = get_project_settings()

process = CrawlerProcess(settings)

process.crawl('github_stars')
process.crawl('pocket')
process.crawl('twitter_favs')

process.start()
