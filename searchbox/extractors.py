from scrapy.http import HtmlResponse, TextResponse
import validators
from mimeparse import parse_mime_type
import extruct
from w3lib.html import get_base_url
from typing import Optional, Any, Dict, Iterable, Iterable


def fix_url(url):
    if not url:
        return None

    if validators.url(url):
        return url

    fixed = 'http://' + url
    if validators.url(fixed):
        return fixed

    return None


def is_github_html(response):
    content_type = response.headers['Content-Type'].decode('utf-8')
    parts = parse_mime_type(content_type)
    return len(parts) > 1 and parts[0] == 'application' and \
        parts[1].startswith('vnd.github.') and parts[1].endswith('.html')


def body_text(response):
    if response is None:
        return None

    text_data = None
    title = None
    html = None

    if isinstance(response, HtmlResponse) or is_github_html(response):
        text_data = '\n'.join(
            response.xpath("//body//text()").extract()).strip()
        title = ' '.join(
            response.xpath("//head/title//text()").extract()).strip()
        html = response.text
    elif isinstance(response, TextResponse):
        text_data = response.text
    else:
        text_data = None

    # 20MB assuming 2 bytes per character, not the worst possible case for UTF-8 since some
    # characters encode as 4 bytes, but pretty safe based on normal text
    max_length = 10485760
    if text_data and len(text_data) > max_length:
        text_data = text_data[:max_length]

    return (title, text_data, html)


def is_processable(response):
    status_ok = response.status < 400 and response.status != 304
    is_cached = 'cached' in response.flags
    return status_ok and not is_cached


def normalise_tag(tag_source: str) -> Iterable[str]:
    if tag_source is None:
        return

    base_tag = tag_source.strip().lower().replace(' ', '_').replace(
        '-', '_').replace('[', '').replace(']', '')
    parts = base_tag.split(':')
    if parts[0] == 'tag' or parts[0] == 'section' \
       or parts[0] == 'topic' or parts[0] == 'category' \
       or parts[0] == 'プラットフォーム' or parts[0] == 'subject':
        parts = parts[1:]

    # Some sites use tags as general attributes, eg. lite:true, elevated:false, etc...
    # we'll ignore those
    if len(parts) > 1:
        return

    base_tag = parts[0].strip()
    if base_tag:
        yield base_tag


class MicroformatExtractor(object):
    def __init__(self,
                 url: str,
                 html: Optional[str] = None,
                 metadata: Optional[Dict[str, Any]] = None):
        if metadata is None:
            if html is None:
                raise Exception(
                    "Either a html document or a metadata dictionary must be provided"
                )
            base_url = get_base_url(html, url)
            self.data = extruct.extract(html, base_url=base_url)
        else:
            self.data = metadata

    def get_tags(self):
        def parse_tag_list(list_or_str) -> Iterable[str]:
            if isinstance(list_or_str, list):
                for tag in list_or_str:
                    yield from normalise_tag(tag)
            else:
                for tag in list_or_str.split(','):
                    yield from normalise_tag(tag)

        if 'json-ld' in self.data:
            for element in self.data['json-ld']:
                if 'keywords' in element:
                    for keyword in parse_tag_list(element['keywords']):
                        yield keyword
                if 'mainEntity' in element and 'keywords' in element[
                        'mainEntity']:
                    for keyword in parse_tag_list(
                            element['mainEntity']['keywords']):
                        yield keyword

        if 'rdfa' in self.data:

            def iterate_tags(rdfa_element, attribute):
                for protocol in ['http', 'https']:
                    key = "{}:{}".format(protocol, attribute)
                    if key in rdfa_element:
                        for tag in rdfa_element[key]:
                            if '@value' in tag:
                                yield from normalise_tag(tag['@value'])

            for element in self.data['rdfa']:
                yield from iterate_tags(element, 'ogp.me/ns/article#tag')
                yield from iterate_tags(element, 'ogp.me/ns/video#tag')
                yield from iterate_tags(element, 'ogp.me/ns/article#tag')
                yield from iterate_tags(element, 'ogp.me/ns#tags')
                yield from iterate_tags(element, 'ogp.me/ns#tag')
                yield from iterate_tags(element, 'ogp.me/ns/book#tag')

        if 'microdata' in self.data:
            if 'keywords' in self.data['microdata']:
                keywords = self.data['microdata']['keywords']
                for tag in parse_tag_list(keywords):
                    yield tag

        if 'opengraph' in self.data:
            if 'article:tag' in self.data['opengraph']:
                for tag in parse_tag_list(
                        self.data['opengraph']['article:tag']):
                    yield tag
