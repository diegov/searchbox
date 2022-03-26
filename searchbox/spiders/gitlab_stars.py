# -*- coding: utf-8 -*-
import json
import logging

import scrapy
from scrapy.http import JsonRequest

from ..extractors import (body_text, extract_next_page_link, fix_url,
                          get_links_from_markdown, get_text_from_html,
                          get_text_from_markdown, is_processable)
from ..items import CrawlItem
from ..secrets_loader import SECRETS

usernames = SECRETS.gitlab['users_to_crawl']
token = SECRETS.gitlab['personal_access_token']


class GitlabStarsSpider(scrapy.Spider):
    name = 'gitlab_stars'
    handle_httpstatus_list = [x for x in range(400, 600)]

    def _prepare_json_request(self, url: str, callback: any) -> JsonRequest:
        req = JsonRequest(url=url, callback=callback)
        req.headers['PRIVATE-TOKEN'] = token
        # API call, don't need to check robots
        req.meta['dont_obey_robotstxt'] = True
        return req

    def start_requests(self):
        for username in usernames:
            template = 'https://gitlab.com/api/v4/users?username={}'
            url = template.format(username)
            yield self._prepare_json_request(url, self.parse_user)

    def parse_user(self, response):
        if not is_processable(response, process_cached=True):
            return

        users = json.loads(response.text)
        for user in users:
            template = 'https://gitlab.com/api/v4/users/{}/starred_projects?per_page=1'
            url = template.format(user['id'])
            yield self._prepare_json_request(url, self.parse_stars)

    def parse_stars(self, response):
        if not is_processable(response, process_cached=True):
            return

        try:
            next_page_url = extract_next_page_link(response.headers)
            if next_page_url is not None:
                yield self._prepare_json_request(next_page_url,
                                                 self.parse_stars)
        except Exception as e:
            logging.log(logging.ERROR, 'Failed to get next page url', e)

        items = json.loads(response.text)
        for starred in items:
            web_url = starred['web_url']
            name = starred['name']
            description_md = starred['description']
            description = get_text_from_markdown(response, description_md)
            star_item = CrawlItem(name=name, description=description,
                                  url=web_url)

            if 'last_activity_at' in starred:
                star_item['last_update'] = starred['last_activity_at']

            if 'tag_list' in starred:
                star_item['repository_tags'] = starred['tag_list']

            yield star_item

            if 'readme_url' in starred:
                url = starred['readme_url'] + '?format=json'
                readme_req = scrapy.Request(url=url,
                                            callback=self.parse_readme)
                readme_req.meta['url'] = star_item['url']
                yield readme_req

            for homepage in get_links_from_markdown(response, description_md):
                homepage_url = fix_url(homepage)
                if homepage_url:
                    req = scrapy.Request(url=homepage_url,
                                         callback=self.parse_homepage)
                    req.meta['gitlab_url'] = star_item['url']
                    yield req

    def parse_readme(self, response):
        if is_processable(response):
            url = response.meta['url']
            readme = json.loads(response.text)
            html = readme['html']
            content = get_text_from_html(response, html, is_snippet=True)
            yield CrawlItem(url=url, content=content, html=html)

    def parse_homepage(self, response):
        if not is_processable(response):
            return

        url = response.url
        gitlab_url = response.meta['gitlab_url']

        title, content, html = body_text(response)
        item = CrawlItem(url=url, repository_backlink=gitlab_url,
                         content=content, html=html)
        if title:
            item['name'] = title
        yield item
