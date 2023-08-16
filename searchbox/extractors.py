import datetime
from typing import Any, Callable, Dict, Generator, Iterable, List, Optional, Tuple, TypeVar, Union
from urllib.parse import urljoin, urlsplit, urlunsplit

import dateutil.parser
import extruct
import links_from_header
import markdown
import parsel
from scrapy.core.engine import Response
import scrapy.utils.response as scrapy_response
import validators
from lxml import etree
from mimeparse import parse_mime_type
from scrapy.http import HtmlResponse, TextResponse
from w3lib.html import get_base_url

TEXT_XPATH = "//body//text()"


def fix_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return None

    if validators.url(url):
        return url

    fixed = 'http://' + url
    if validators.url(fixed):
        return fixed

    return None


def is_github_html(response: Response) -> bool:
    content_type = None
    if 'Content-Type' in response.headers:
        content_type = (response.headers['Content-Type'] or b'').decode('utf-8')
    elif 'content-type' in response.headers:
        content_type = (response.headers['content-type'] or b'').decode('utf-8')

    if content_type is None:
        return False

    parts = parse_mime_type(content_type)
    return len(parts) > 1 and parts[0] == 'application' and \
        parts[1].startswith('vnd.github.') and parts[1].endswith('.html')


def body_text(response: Optional[Response]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    if response is None:
        return (None, None, None)

    text_data = None
    title = None
    html = None

    if isinstance(response, HtmlResponse) or is_github_html(response):
        text_data = '\n'.join(
            x.strip()
            for x in response.xpath(TEXT_XPATH).extract()).strip()
        title = ' '.join(
            x.strip()
            for x in response.xpath("//head/title//text()").extract()).strip()
        html = response.text
    elif isinstance(response, TextResponse):
        text_data = response.text
    else:
        text_data = None

    # 20MB assuming 2 bytes per character, not the worst possible case for
    # UTF-8 since some characters encode as 4 bytes, but pretty safe based
    # on normal text
    max_length = 10485760
    if text_data and len(text_data) > max_length:
        text_data = text_data[:max_length]

    return (title, text_data, html)


def is_processable(response: Response, process_cached: bool = False) -> bool:
    status_ok = response.status < 400 and response.status != 304
    is_cached = 'cached' in response.flags
    return status_ok and (process_cached or not is_cached)


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

    # Some sites use tags as general attributes, eg. lite:true, elevated:false,
    # etc... we'll ignore those
    if len(parts) > 1:
        return

    base_tag = parts[0].strip()
    if base_tag:
        yield base_tag


T = TypeVar('T')


def filter_none(elements: Iterable[T]) -> Generator[T, None, None]:
    return (x for x in elements if x is not None)


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

    def get_published_date(self) -> Optional[datetime.datetime]:
        def get_attribute_list() -> Generator[str, None, None]:
            if 'rdfa' in self.data:
                for element in filter_none(self.data['rdfa']):
                    yield from iterate_rdfa_tags(
                        element, 'ogp.me/ns/article#published_time')

            json_ld_elements = self.data.get('json-ld')
            if json_ld_elements:
                for element in filter_none(json_ld_elements):
                    if 'datePublished' in element and json_ld_matches_url(
                            element, self.url, match_by_default=True):
                        yield from iterate_elements(element['datePublished'])

                    graph_elements = element.get('@graph')
                    if graph_elements:
                        for graph_element in filter_none(graph_elements):
                            if 'datePublished' in graph_element and \
                               json_ld_matches_url(graph_element, self.url):
                                yield from iterate_elements(
                                    graph_element['datePublished'])

        for candidate in filter_none(get_attribute_list()):
            dt = try_parse_date(candidate)
            if dt is not None:
                return dt

        return None

    def get_tags(self) -> Iterable[str]:
        if 'json-ld' in self.data:
            yield from get_json_ld_tags(self.data['json-ld'])

        if 'rdfa' in self.data:
            yield from get_rdfa_tags(self.data['rdfa'])

        if 'microdata' in self.data:
            if 'keywords' in self.data['microdata']:
                keywords = self.data['microdata']['keywords']
                for tag in filter_none(parse_tag_list(keywords)):
                    yield tag

        if 'opengraph' in self.data:
            if 'article:tag' in self.data['opengraph']:
                for tag in filter_none(parse_tag_list(
                        self.data['opengraph']['article:tag'])):
                    yield tag


def compare_urls(a: str, b: str, ignore_protocol: bool = True) -> bool:
    def fix_path(path: str) -> str:
        if path.endswith('/'):
            return path[:-1]
        return path

    def parse_url(url: str, ignore_protocol: bool) -> Optional[str]:
        fixed = fix_url(url)
        if fixed is None:
            return None

        result = (*urlsplit(fixed),)
        if ignore_protocol:
            result = ('', *result[1:])

        result = (result[0], result[1], fix_path(result[2]), *result[3:])

        return urlunsplit(result)

    url_a = parse_url(a, ignore_protocol)
    url_b = parse_url(b, ignore_protocol)

    if url_a is None or url_b is None:
        return a == b

    return url_a == url_b


def get_json_ld_tags(data: List[Dict[str, Any]]) -> Iterable[str]:
    for element in filter_none(data):
        if 'keywords' in element:
            for keyword in filter_none(parse_tag_list(element['keywords'])):
                yield keyword
        if 'mainEntity' in element and 'keywords' in element['mainEntity']:
            for keyword in filter_none(parse_tag_list(
                    element['mainEntity']['keywords'])):
                yield keyword


def get_rdfa_tags(data: List[Dict[str, Any]]) -> Generator[str, None, None]:
    for element in filter_none(data):
        yield from iterate_rdfa_tags(element, 'ogp.me/ns/article#tag',
                                     preprocess=normalise_tag)
        yield from iterate_rdfa_tags(element, 'ogp.me/ns/article#tags',
                                     preprocess=normalise_tag)
        yield from iterate_rdfa_tags(element, 'ogp.me/ns/video#tag',
                                     preprocess=normalise_tag)
        yield from iterate_rdfa_tags(element, 'ogp.me/ns#tags',
                                     preprocess=normalise_tag)
        yield from iterate_rdfa_tags(element, 'ogp.me/ns#tag',
                                     preprocess=normalise_tag)
        yield from iterate_rdfa_tags(element, 'ogp.me/ns/book#tag',
                                     preprocess=normalise_tag)
    

def iterate_rdfa_tags(
        rdfa_element: Dict[str, Any],
        attribute: str,
        preprocess: Optional[Callable[[str], Iterable[str]]] = None
) -> Generator[str, None, None]:
    for protocol in ['http', 'https']:
        key = "{}://{}".format(protocol, attribute)
        if key in rdfa_element:
            for tag in filter_none(rdfa_element[key]):
                if '@value' in tag:
                    if preprocess is not None:
                        yield from preprocess(tag['@value'])
                    else:
                        yield tag['@value']


def json_ld_matches_url(element: Dict[str, Any], url: str, match_by_default: bool = False) -> bool:
    if 'url' in element:
        return compare_urls(element['url'], url, ignore_protocol=True)

    if '@id' in element:
        return compare_urls(element['@id'], url, ignore_protocol=True)

    return match_by_default


def iterate_elements(list_or_obj: Union[List[T], T]) -> Generator[T, None, None]:
    if isinstance(list_or_obj, list):
        for element in list_or_obj:
            yield element
    else:
        yield list_or_obj


def parse_tag_list(list_or_str: Union[List[Any], str]) -> Generator[str, None, None]:
    if isinstance(list_or_str, list):
        for tag in filter_none(list_or_str):
            yield from normalise_tag(tag)
    else:
        for tag in filter_none(list_or_str.split(',')):
            yield from normalise_tag(tag)


def try_parse_date(dt_str: str) -> Optional[datetime.datetime]:
    cleaned_up = dt_str.replace(' +0000 ', ' UTC ')
    attempts: List[Callable[[str], datetime.datetime]] = [
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
        except Exception:
            pass

    return None


def get_text_from_markdown(response: TextResponse,
                           content: str) -> str:
    html = _md_to_html_doc(content)
    return get_text_from_html(response, html)


def get_text_from_html(response: TextResponse,
                       html: str, is_snippet: bool = False) -> str:
    base_url = scrapy_response.get_base_url(response)
    if is_snippet:
        html = '<html>{}</html>'.format(html)
    selector = parsel.Selector(text=html, base_url=base_url)
    return ' '.join(x.strip() for x in
                    selector.xpath(TEXT_XPATH).extract()).strip()


def get_links_from_markdown(response: TextResponse,
                            content: str) -> Iterable[str]:
    # TODO: Why is this, or its body, null at times?
    if not content:
        return
    html = _md_to_html_doc(content)
    yield from get_links_from_html(response, html)


def get_links_from_html(response: TextResponse, html: str) -> Iterable[str]:
    base_url = scrapy_response.get_base_url(response)
    doc = etree.fromstring(html, base_url=base_url)
    for link in doc.xpath('//a'):
        url = link.get('href')
        full_url = urljoin(base_url, url)
        if full_url.startswith('http:') or full_url.startswith('https:'):
            yield full_url


def _md_to_html_doc(content: str) -> str:
    doc_content = markdown.markdown(content, output_format='html')
    return '<html>{}</html>'.format(doc_content)


def extract_next_page_link(headers: Dict[Any, Any]) -> Optional[str]:
    links = None
        
    if b'Link' in headers:
        links = headers[b'Link']
    elif 'Link' in headers:
        links = headers['Link']
    elif b'link' in headers:
        links = headers[b'link']
    elif 'link' in headers:
        links = headers['link']
    else:
        # Try all possible casings
        for header in headers.keys():
            header_name = header
            if isinstance(header, bytes):
                header_name = header.decode('utf-8')
            if header_name.lower() == 'link':
                links = headers[header]
                break

    if links is None:
        return None
    elif isinstance(links, bytes):
        links = links.decode('utf-8')

    results: Dict[str, str] = links_from_header.extract(links)

    if 'next' in results:
        return results['next']
    else:
        return None
