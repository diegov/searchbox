# -*- coding: utf-8 -*-
import re
import json
from typing import Callable, Optional

import scrapy
from scrapy.core.engine import Response
from scrapy.http import JsonRequest, Request

from ..types import SpiderItems, SpiderRequests, SpiderResults

from ..extractors import (body_text, extract_next_page_link, fix_url,
                          is_processable)
from ..items import CrawlItem
from ..secrets_loader import SECRETS

usernames = SECRETS.github['users_to_crawl']


class GithubURLMatcher:
    def __init__(self, spider: 'GithubStarsSpider'):
        self.spider = spider
        self.gist_expression = '^http(s)?://gist.github.com/([^/]+)/([^/]+)(/)?$'
        self.repo_expression = '^http(s)?://(www\\.)?github.com/([^/]+)/([^/]+)(/)?$'
        # TODO: Ignore query string

    def __call__(self, r: Request) -> SpiderRequests:
        m = re.match(self.gist_expression, r.url)
        if m:
            gist_owner: str  = m.group(3)
            gist_id: str = m.group(4)
            gist_item_url = 'https://gist.github.com/{}/{}'.format(gist_owner, gist_id)
            gist_api_url = 'https://api.github.com/gists/{}'.format(gist_id)

            yield from self.spider.get_gist_details(gist_api_url, CrawlItem(url=gist_item_url))
            return

        m = re.match(self.repo_expression, r.url)
        if m:
            owner: str  = m.group(3)
            repo: str = m.group(4)
            item_url = 'https://github.com/{}/{}'.format(owner, repo)
            api_url = 'https://api.github.com/repos/{}/{}'.format(owner, repo)

            yield from self.spider.get_repo_details(api_url, CrawlItem(url=item_url))


class GithubStarsSpider(scrapy.Spider):  # type: ignore
    name = 'github_stars'
    http_user = SECRETS.github['username']
    http_pass = SECRETS.github['personal_access_token']
    http_auth_domain = 'api.github.com'

    handle_httpstatus_list = [x for x in range(400, 600)]

    def get_url_matcher(self) -> Callable[[Request], SpiderRequests]:
        return GithubURLMatcher(self)

    def start_requests(self) -> SpiderRequests:
        # Starred gists are only provided for the authenticated in user
        yield self._api_request('https://api.github.com/gists/starred', self.parse_gist_stars)

        urls = ['https://api.github.com/users/{}/starred'.format(name) for name in usernames]
        for url in urls:
            yield self._api_request(url, self.parse_stars)

    def _api_request(self, url: str, callback: Callable[[Response], SpiderResults],
                      item: Optional[CrawlItem] = None) -> JsonRequest:
        req = JsonRequest(url=url, callback=callback)
        req.headers['Accept'] = 'application/vnd.github+json'
        req.headers['X-GitHub-Api-Version'] = "2022-11-28"

        # API call, don't need to check robots
        req.meta['dont_obey_robotstxt'] = True
        if item is not None:
            req.meta['item'] = item
        return req

    def get_repo_details(self, api_url: str, item: CrawlItem) -> SpiderRequests:
        yield self._api_request(api_url, self.parse_repo, item=item)

    def get_gist_details(self, api_url: str, item: CrawlItem) -> SpiderRequests:
        yield self._api_request(api_url, self.parse_gist, item=item)

    def parse_stars(self, response: Response) -> SpiderResults:
        if not is_processable(response, process_cached=True):
            return

        items = json.loads(response.text)
        for starred in items:
            api_url = starred['url']
            html_url = starred['html_url']
            name = starred['name']
            description = starred['description']
            star_item = CrawlItem(name=name, description=description,
                                  url=html_url)
            yield from self.get_repo_details(api_url, star_item)

        next_page_url = extract_next_page_link(response.headers)
        if next_page_url is not None:
            yield self._api_request(next_page_url, self.parse_stars)

    def parse_readme(self, response: Response) -> SpiderItems:
        if is_processable(response):
            # Ignore title, we get it from the API
            _, content, html = body_text(response)
            url = response.meta['url']
            item = CrawlItem(url=url, content=content, html=html)

            yield item

    def parse_repo(self, response: Response) -> SpiderResults:
        star_item: CrawlItem = response.meta['item']

        if not is_processable(response):
            yield star_item
            return

        item = json.loads(response.text)

        last_update = item['updated_at']
        
        star_item.last_update = last_update

        if 'topics' in item:
            star_item.repository_tags = item['topics']

        star_item.name = star_item.name or item.get('name')
        star_item.description = star_item.description or item.get('description')

        yield star_item

        readme_url = item['url'] + '/readme'
        readme_req = scrapy.Request(url=readme_url, callback=self.parse_readme, headers={"Accept": "application/vnd.github.v3.html"})

        readme_req.meta['url'] = star_item.url
        yield readme_req
        
        if 'homepage' in item:
            homepage_url = fix_url(item['homepage'])
            if homepage_url:
                req = scrapy.Request(url=homepage_url, callback=self.parse_homepage)
                req.meta['github_url'] = star_item.url
                yield req

    def parse_gist_stars(self, response: Response) -> SpiderResults:
        if not is_processable(response, process_cached=True):
            return

        items = json.loads(response.text)
        for starred in items:
            api_url = starred['url']
            html_url = starred['html_url']
            name = starred['description']
            star_item = CrawlItem(name=name, description='', url=html_url)
            yield from self.get_gist_details(api_url, star_item)

        next_page_url = extract_next_page_link(response.headers)
        if next_page_url is not None:
            yield self._api_request(next_page_url, self.parse_gist_stars)

    def parse_gist(self, response: Response) -> SpiderResults:
        star_item: CrawlItem = response.meta['item']

        if not is_processable(response):
            yield star_item
            return

        item = json.loads(response.text)

        last_update = item['updated_at']

        star_item.last_update = last_update

        if 'topics' in item:
            star_item.repository_tags = item['topics']

        star_item.name = star_item.name or item.get('name')
        star_item.description = star_item.description or item.get('description')

        yield star_item

        html_url = item.get('html_url')
        if html_url:
            html_req = scrapy.Request(url=html_url, callback=self.parse_gist_html)
            html_req.meta['url'] = star_item.url
            yield html_req

    def parse_gist_html(self, response: Response) -> SpiderItems:
        if not is_processable(response):
            return

        _, content, html = body_text(response)
        url = response.meta['url']
        item = CrawlItem(url=url, content=content, html=html)

        yield item

    def parse_homepage(self, response: Response) -> SpiderItems:
        if not is_processable(response):
            return

        url = response.url
        github_url = response.meta['github_url']

        title, content, html = body_text(response)
        item = CrawlItem(url=url, repository_backlink=github_url, content=content, html=html)
        if title:
            item.name = title
        yield item
