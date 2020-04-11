# -*- coding: utf-8 -*-
import scrapy
from scrapy.http import JsonRequest
import json
import links_from_header

from ..secrets_loader import SECRETS
from ..items import CrawlItem
from ..extractors import body_text, is_processable, fix_url

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

        items = json.loads(response.body_as_unicode())
        for starred in items:
            api_url = starred['url']
            html_url = starred['html_url']
            name = starred['name']
            description = starred['description']
            star_item = CrawlItem(name=name, description=description, url=html_url)
            req = JsonRequest(url=api_url, callback=self.parse_repo)
            req.meta['item'] = star_item
            req.meta['dont_obey_robotstxt'] = True
            yield req

        next_page_url = self.extract_next_page(response.headers)
        if next_page_url is not None:
            req = JsonRequest(url=next_page_url, callback=self.parse_stars)
            req.meta['dont_obey_robotstxt'] = True
            yield req

    def parse_readme(self, response):
        if is_processable(response):
            # Ignore title, we get it from the API
            _, content = body_text(response)
            url = response.meta['url']
            item = CrawlItem(url=url, content=content)

            yield item

    def parse_repo(self, response):
        star_item = response.meta['item']

        if not is_processable(response):
            yield star_item
            return

        item = json.loads(response.body_as_unicode())

        # TODO: Topics API is in beta, update this to incldue topics once that's stable
        # https://developer.github.com/v3/repos#list-all-topics-for-a-repository
        
        last_update = item['updated_at']
        
        star_item['last_update'] = last_update

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

        title, content = body_text(response)
        item = CrawlItem(url=url, github_backlink=github_url, content=content)
        if title:
            item['name'] = title
        yield item

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
        else:
            return None
