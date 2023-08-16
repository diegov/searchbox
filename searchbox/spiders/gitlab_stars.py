# -*- coding: utf-8 -*-
import json
import logging
import re
from typing import Any, Callable, Dict, List, Optional
import urllib.parse

import scrapy
from scrapy.core.engine import Response
from scrapy.http import JsonRequest, TextResponse

from ..types import SpiderItems, SpiderRequests, SpiderResults

from ..extractors import (body_text, extract_next_page_link, fix_url,
                          get_links_from_markdown, get_text_from_html,
                          get_text_from_markdown, is_processable)
from ..items import CrawlItem
from ..secrets_loader import SECRETS

usernames = SECRETS.gitlab['users_to_crawl']
token = SECRETS.gitlab['personal_access_token']


class GitlabURLMatcher:
    def __init__(self, spider: 'GitlabStarsSpider'):
        self.spider = spider
        self.expression = '^http(s)?://(www\\.)?gitlab.com/([^/]+)/([^/]+)(/)?$'
        # TODO: Ignore query string

    def __call__(self, r: scrapy.Request) -> SpiderRequests:
        m = re.match(self.expression, r.url)
        if m:
            owner: str  = m.group(3)
            repo: str = m.group(4)

            # User pages in github have the format https://gitlab.com/users/...
            # We don't want those
            if owner != 'users':
                yield from self.spider.get_repo_details(r.url, owner, repo)


class GitlabStarsSpider(scrapy.Spider):  # type: ignore
    name = 'gitlab_stars'
    handle_httpstatus_list = [x for x in range(400, 600)]

    def get_url_matcher(self) -> Callable[[scrapy.Request], SpiderRequests]:
        return GitlabURLMatcher(self)

    def _prepare_json_request(self, url: str, callback: Any, meta: Dict[str, Any] = {}) -> JsonRequest:
        req = JsonRequest(url=url, callback=callback)
        req.headers['PRIVATE-TOKEN'] = token
        # API call, don't need to check robots
        req.meta['dont_obey_robotstxt'] = True

        for k, v in meta.items():
            req.meta[k] = v

        return req

    def start_requests(self) -> SpiderRequests:
        for username in usernames:
            template = 'https://gitlab.com/api/v4/users?username={}'
            url = template.format(username)
            yield self._prepare_json_request(url, self.parse_user)

    def parse_user(self, response: Response) -> SpiderRequests:
        if not is_processable(response, process_cached=True):
            return

        users = json.loads(response.text)
        for user in users:
            template = 'https://gitlab.com/api/v4/users/{}/starred_projects?per_page=1'
            url = template.format(user['id'])
            yield self._prepare_json_request(url, self.parse_stars)

    def parse_stars(self, response: TextResponse) -> SpiderResults:
        if not is_processable(response, process_cached=True):
            return

        try:
            next_page_url = extract_next_page_link(response.headers)
            if next_page_url is not None:
                yield self._prepare_json_request(next_page_url,
                                                 self.parse_stars)
        except Exception as e:
            logging.log(logging.ERROR, 'Failed to get next page url', e)

        items: List[Dict[str, Any]] = json.loads(response.text)
        for starred in items:
            yield from self._parse_repo_details(response, starred)

    def get_repo_details(self, url: str, owner: str, repo: str) -> SpiderRequests:
        project_id = urllib.parse.quote("{}/{}".format(owner, repo), safe='')
        api_url = 'https://gitlab.com/api/v4/projects/{}'.format(project_id)
        yield self._prepare_json_request(api_url, self.parse_repo_details,
                                         meta={'url': url})

    def parse_repo_details(self, response: TextResponse) -> SpiderResults:
        if not is_processable(response):
            return

        starred_item = json.loads(response.text)
        yield from self._parse_repo_details(response, starred_item)

    def _parse_repo_details(self, response: TextResponse, starred: Dict[str, Any]) -> SpiderResults:
        web_url = response.meta.get('url') or starred['web_url']
        name = starred['name']
        description_md = starred['description']
        if description_md:
            description = get_text_from_markdown(response, description_md)
        else:
            description = ''
        star_item = CrawlItem(name=name, description=description,
                              url=web_url)

        if 'last_activity_at' in starred:
            star_item.last_update = starred['last_activity_at']

        if 'tag_list' in starred:
            star_item.repository_tags = starred['tag_list']

        yield star_item

        if 'readme_url' in starred:
            url = starred['readme_url'] + '?format=json'
            readme_req = scrapy.Request(url=url,
                                        callback=self.parse_readme)
            readme_req.meta['url'] = star_item.url
            yield readme_req

        for homepage in get_links_from_markdown(response, description_md):
            homepage_url = fix_url(homepage)
            if homepage_url:
                req = scrapy.Request(url=homepage_url,
                                     callback=self.parse_homepage)
                req.meta['gitlab_url'] = star_item.url
                yield req

    def parse_readme(self, response: TextResponse) -> SpiderItems:
        if is_processable(response):
            url = response.meta['url']
            readme = json.loads(response.text)
            html = readme['html']
            content = get_text_from_html(response, html, is_snippet=True)
            yield CrawlItem(url=url, content=content, html=html)

    def parse_homepage(self, response: Response) -> SpiderItems:
        if not is_processable(response):
            return

        url = response.url
        gitlab_url = response.meta['gitlab_url']

        title, content, html = body_text(response)
        item = CrawlItem(url=url, repository_backlink=gitlab_url,
                         content=content, html=html)
        if title:
            item.name = title
        yield item
