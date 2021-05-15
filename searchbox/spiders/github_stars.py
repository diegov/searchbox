# -*- coding: utf-8 -*-
import json

import scrapy
from scrapy.http import JsonRequest

from ..extractors import (body_text, extract_next_page_link, fix_url,
                          is_processable)
from ..items import CrawlItem
from ..secrets_loader import SECRETS

usernames = SECRETS.github['users_to_crawl']


class GithubStarsSpider(scrapy.Spider):
    name = 'github_stars'
    http_user = SECRETS.github['username']
    http_pass = SECRETS.github['personal_access_token']
    handle_httpstatus_list = [x for x in range(400, 600)]

    def start_requests(self):
        urls = ['https://api.github.com/users/{}/starred'.format(name) for name in usernames]
        for url in urls:
            req = JsonRequest(url=url, callback=self.parse_stars)
            # API call, don't need to check robots
            req.meta['dont_obey_robotstxt'] = True
            yield req

    def parse_stars(self, response):
        if not is_processable(response):
            return

        items = json.loads(response.text)
        for starred in items:
            api_url = starred['url']
            html_url = starred['html_url']
            name = starred['name']
            description = starred['description']
            star_item = CrawlItem(name=name, description=description,
                                  url=html_url)
            req = JsonRequest(url=api_url, callback=self.parse_repo)
            req.meta['item'] = star_item
            req.meta['dont_obey_robotstxt'] = True
            yield req

        next_page_url = extract_next_page_link(response.headers)
        if next_page_url is not None:
            req = JsonRequest(url=next_page_url, callback=self.parse_stars)
            req.meta['dont_obey_robotstxt'] = True
            yield req

    def parse_readme(self, response):
        if is_processable(response):
            # Ignore title, we get it from the API
            _, content, html = body_text(response)
            url = response.meta['url']
            item = CrawlItem(url=url, content=content, html=html)

            yield item

    def parse_repo(self, response):
        star_item = response.meta['item']

        if not is_processable(response):
            yield star_item
            return

        item = json.loads(response.text)

        last_update = item['updated_at']
        
        star_item['last_update'] = last_update

        if 'topics' in item:
            star_item['repository_tags'] = item['topics']

        yield star_item

        readme_url = item['url'] + '/readme'
        readme_req = scrapy.Request(url=readme_url, callback=self.parse_readme, headers={"Accept": "application/vnd.github.v3.html"})

        readme_req.meta['url'] = star_item['url']
        yield readme_req
        
        if 'homepage' in item:
            homepage_url = fix_url(item['homepage'])
            if homepage_url:
                req = scrapy.Request(url=homepage_url, callback=self.parse_homepage)
                req.meta['github_url'] = star_item['url']
                yield req

    def parse_homepage(self, response):
        if not is_processable(response):
            return

        url = response.url
        github_url = response.meta['github_url']

        title, content, html = body_text(response)
        item = CrawlItem(url=url, repository_backlink=github_url, content=content, html=html)
        if title:
            item['name'] = title
        yield item
