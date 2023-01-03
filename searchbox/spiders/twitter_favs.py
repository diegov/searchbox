# -*- coding: utf-8 -*-
from typing import Generator, Optional, Union
import scrapy
from scrapy.core.engine import Response
from scrapy.http import Request
from twitter import OAuth
import json

from ..secrets_loader import SECRETS
from ..extractors import body_text, is_processable, try_parse_date
from ..items import CrawlItem

RESULTS_PER_REQUEST = 100


class TwitterFavsSpider(scrapy.Spider):  # type: ignore
    name = 'twitter_favs'

    consumer_key = SECRETS.twitter['consumer_key']
    consumer_secret = SECRETS.twitter['consumer_secret']
    access_token_key = SECRETS.twitter['access_token_key']
    access_token_secret = SECRETS.twitter['access_token_secret']

    def start_requests(self) -> Generator[Request, None, None]:
        yield self.make_favourites_request()

    def make_favourites_request(self, max_id: Optional[int] = None) -> Request:
        params = {'count': str(RESULTS_PER_REQUEST),
                  'tweet_mode': 'extended'}
        if max_id is not None:
            params['max_id'] = str(max_id)

        auth = OAuth(TwitterFavsSpider.access_token_key,
                     TwitterFavsSpider.access_token_secret,
                     TwitterFavsSpider.consumer_key,
                     TwitterFavsSpider.consumer_secret)

        url = 'https://api.twitter.com/1.1/favorites/list.json'
        qs_part = auth.encode_params(url, 'GET', params)
        final_url = url + '?' + qs_part
        req = Request(url=final_url, callback=self.parse_favourites)
        # This is an authorised API call we don't need to check robots.txt
        req.meta['dont_obey_robotstxt'] = True
        return req

    def parse_favourites(
            self,
            response: Response
    ) -> Generator[Union[Request, CrawlItem], None, None]:
        if not is_processable(response):
            return

        result = json.loads(response.text)
        if len(result) == 0:
            return

        for fav in result:
            hashtags = [h['text'] for h in fav['entities']['hashtags']] if 'entities' in fav and 'hashtags' in fav['entities'] else None
            content = fav['full_text']

            # Strange we don't have this in the response
            url = 'https://twitter.com/{}/status/{}'.format(fav['user']['screen_name'], fav['id'])
            date_str = fav['created_at']
            created_at = try_parse_date(date_str)
            last_update = created_at.isoformat() if created_at else None

            if hashtags:
                yield CrawlItem(url=url, content=content, last_update=last_update, twitter_tags=hashtags)
            else:
                yield CrawlItem(url=url, content=content, last_update=last_update)

            for linked_url in fav['entities']['urls']:
                # TODO: check if this is another tweet, and fetch through API instead
                final_url = url=linked_url['expanded_url']
                req = scrapy.Request(final_url, callback=self.parse_webpage)
                # Tracked in case we follow redirects
                req.meta['url'] = final_url
                req.meta['twitter_url'] = url
                yield req


        max_id = result[len(result) - 1]['id'] - 1
        yield self.make_favourites_request(max_id=max_id)


    def parse_webpage(self, response: Response) -> Generator[CrawlItem, None, None]:
        if not is_processable(response):
            return
        url = response.meta['url']
        twitter_url = response.meta['twitter_url']
        title, content, html = body_text(response)
        item = CrawlItem(url=url, content=content, twitter_backlink=twitter_url, html=html)
        if title:
            item['name'] = title
        yield item
