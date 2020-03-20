# -*- coding: utf-8 -*-
import scrapy
from scrapy.link import Link
from scrapy.http import JsonRequest
import json
import re
import links_from_header

from ..secrets_loader import SECRETS
from ..items import CrawlItem
from ..extractors import *

usernames = SECRETS.github['users_to_crawl']

class GithubStarsSpider(scrapy.Spider):
    name = 'github_stars'
    http_user = SECRETS.github['username']
    http_pass = SECRETS.github['personal_access_token']
    handle_httpstatus_list = [x for x in range(400, 600)]

    def start_requests(self):
        urls = ['https://api.github.com/users/{}/starred'.format(name) for name in usernames]
        for url in urls:
            yield JsonRequest(url=url, callback=self.parse_stars)

    def parse_stars(self, response):
        if response.status >= 400:
            return
        
        items = json.loads(response.body_as_unicode())
        for starred in items:
            api_url = starred['url']
            html_url = starred['html_url']
            name = starred['name']
            description = starred['description']
            req = JsonRequest(url=api_url, callback=self.parse_repo)
            star_item = CrawlItem(name=name, description=description, url=html_url)
            req.meta['item'] = star_item
            yield req

        next_page_url = self.extract_next_page(response.headers)
        if next_page_url is not None:
            yield JsonRequest(url=next_page_url, callback=self.parse_stars)


    def parse_readme(self, response):
        star_item = response.meta['item']

        if response.status < 400:
            star_item['content'] = body_text(response)
        
        if 'homepage_url' in response.meta:
            homepage_url = fix_url(response.meta['homepage_url'])
            if homepage_url:
                req = scrapy.Request(url=homepage_url, callback=self.parse_homepage)
                req.meta['github_url'] = star_item['url']
                yield req
            else:
                yield star_item
        else:
            yield star_item


    def parse_repo(self, response):
        star_item = response.meta['item']

        if response.status >= 400:
            yield star_item
            return
        
        item = json.loads(response.body_as_unicode())

        # TODO: Topics API is in beta, update this to incldue topics once that's stable
        # https://developer.github.com/v3/repos#list-all-topics-for-a-repository
        
        last_update = item['updated_at']
        
        star_item['last_update'] = last_update

        readme_url = item['url'] + '/readme'
        req = scrapy.Request(url=readme_url, callback=self.parse_readme, headers={"Accept": "application/vnd.github.v3.html"})

        req.meta['item'] = star_item
        
        if 'homepage' in item:
            homepage_url = fix_url(item['homepage'])
            if homepage_url:
                req.meta['homepage_url'] = homepage_url

        yield req

    def parse_homepage(self, response):
        if response.status >= 400:
            return

        url = response.url
        github_url = response.meta['github_url']

        content = body_text(response)
        yield CrawlItem(url=url, github_backlink=github_url, content=content)

    def extract_next_page(self, headers):
        links = None
        if b'Link' in headers:
            links = headers[b'Link']
        elif 'Link' in headers:
            links = headers['Link']

        if links is None:
            return None
        elif isinstance(links, bytes):
            links = links.decode('utf-8')

        results = links_from_header.extract(links)
        
        if 'next' in results:
            return results['next']
