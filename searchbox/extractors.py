from scrapy.http import HtmlResponse, TextResponse
import validators
from mimeparse import parse_mime_type
import extruct
from w3lib.html import get_base_url
from typing import Optional, Any, Dict, Iterable, Iterable
from urllib.parse import urlsplit, urlunsplit, SplitResult
import datetime
import dateutil.parser


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


class MicroformatExtractor:
    def __init__(self,
                 url: str,
                 html: Optional[str] = None,
                 metadata: Optional[Dict[str, Any]] = None):
        self.url = url

        if metadata is None:
            if html is None:
                raise Exception(
                    "Either a html document or a metadata dictionary must " +
                    "be provided"
                )
            base_url = get_base_url(html, self.url)
            self.data = extruct.extract(html, base_url=base_url)
        else:
            self.data = metadata

    def get_published_date(self):
        def get_attribute_list():
            if 'rdfa' in self.data:
                for element in self.data['rdfa']:
                    yield from iterate_rdfa_tags(
                        element, 'ogp.me/ns/article#published_time')

            if 'json-ld' in self.data:
                for element in self.data['json-ld']:
                    if 'datePublished' in element and json_ld_matches_url(
                            element, self.url, match_by_default=True):
                        yield from iterate_elements(element['datePublished'])
                    if '@graph' in element:
                        for graph_element in element['@graph']:
                            if 'datePublished' in graph_element and \
                               json_ld_matches_url(graph_element, self.url):
                                yield from iterate_elements(
                                    graph_element['datePublished'])

        for candidate in get_attribute_list():
            dt = try_parse_date(candidate)
            if dt is not None:
                return dt

        return None

    def get_tags(self):
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
            for element in self.data['rdfa']:
                yield from iterate_rdfa_tags(element, 'ogp.me/ns/article#tag', preprocess=normalise_tag)
                yield from iterate_rdfa_tags(element, 'ogp.me/ns/video#tag', preprocess=normalise_tag)
                yield from iterate_rdfa_tags(element, 'ogp.me/ns/article#tag', preprocess=normalise_tag)
                yield from iterate_rdfa_tags(element, 'ogp.me/ns#tags', preprocess=normalise_tag)
                yield from iterate_rdfa_tags(element, 'ogp.me/ns#tag', preprocess=normalise_tag)
                yield from iterate_rdfa_tags(element, 'ogp.me/ns/book#tag', preprocess=normalise_tag)

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


def compare_urls(a: str, b: str, ignore_protocol=True) -> bool:
    def fix_path(path: str) -> str:
        if path.endswith('/'):
            return path[:-1]
        return path

    def parse_url(url: str, ignore_protocol: bool) -> Optional[SplitResult]:
        fixed = fix_url(url)
        if fixed is None:
            return None

        result = urlsplit(fixed)
        if ignore_protocol:
            result = ('', *result[1:])

        result = (result[0], result[1], fix_path(result[2]), *result[3:])

        return urlunsplit(result)

    url_a = parse_url(a, ignore_protocol)
    url_b = parse_url(b, ignore_protocol)

    if url_a is None or url_b is None:
        return a == b

    return url_a == url_b


def iterate_rdfa_tags(rdfa_element, attribute, preprocess=None):
    for protocol in ['http', 'https']:
        key = "{}://{}".format(protocol, attribute)
        if key in rdfa_element:
            for tag in rdfa_element[key]:
                if '@value' in tag:
                    if preprocess is not None:
                        yield from preprocess(tag['@value'])
                    else:
                        yield tag['@value']


def json_ld_matches_url(element, url, match_by_default=False) -> bool:
    if 'url' in element:
        return compare_urls(element['url'], url, ignore_protocol=True)

    if '@id' in element:
        return compare_urls(element['@id'], url, ignore_protocol=True)

    return match_by_default


def iterate_elements(list_or_obj) -> Iterable[Any]:
    if isinstance(list_or_obj, list):
        for element in list_or_obj:
            yield element
    else:
        yield list_or_obj


def parse_tag_list(list_or_str) -> Iterable[str]:
    if isinstance(list_or_str, list):
        for tag in list_or_str:
            yield from normalise_tag(tag)
    else:
        for tag in list_or_str.split(','):
            yield from normalise_tag(tag)


def try_parse_date(dt_str: str) -> datetime.datetime:
    cleaned_up = dt_str.replace(' +0000 ', ' UTC ')
    attempts = [
        # Twitter format
        lambda x: datetime.datetime.strptime(x,
                                             '%a %b %d %H:%M:%S %Z %Y'),
        dateutil.parser.isoparse,
        lambda x: datetime.datetime.strptime(x, '%Y-%m-%d'),
        lambda x: datetime.datetime.strptime(x, '%Y/%m/%d')
    ]
    for attempt in attempts:
        try:
            return attempt(cleaned_up)
        except Exception as ignored:
            pass

    return None
