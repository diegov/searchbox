# -*- coding: utf-8 -*-
import scrapy
from scrapy.http import Request
from twitter import OAuth
import json
from datetime import datetime

from ..secrets_loader import SECRETS
from ..extractors import body_text, is_processable
from ..items import CrawlItem

RESULTS_PER_REQUEST = 100


class TwitterFavsSpider(scrapy.Spider):
    name = 'twitter_favs'

    consumer_key = SECRETS.twitter['consumer_key']
    consumer_secret = SECRETS.twitter['consumer_secret']
    access_token_key = SECRETS.twitter['access_token_key']
    access_token_secret = SECRETS.twitter['access_token_secret']

    def start_requests(self):
        yield self.make_favourites_request()

    def make_favourites_request(self, max_id=None):
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

    def parse_favourites(self, response):
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
            created_at = datetime.strptime(fav['created_at'].replace(' +0000 ',' UTC '), '%a %b %d %H:%M:%S %Z %Y')
            last_update = created_at.isoformat()

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


    def parse_webpage(self, response):
        if not is_processable(response):
            return
        url = response.meta['url']
        twitter_url = response.meta['twitter_url']
        title, content, html = body_text(response)
        item = CrawlItem(url=url, content=content, twitter_backlink=twitter_url, html=html)
        if title:
            item['name'] = title
        yield item
