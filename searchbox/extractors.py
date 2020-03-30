from scrapy.http import HtmlResponse, TextResponse
import validators
from mimeparse import parse_mime_type


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
    
    if isinstance(response, HtmlResponse) or is_github_html(response):
        text_data = '\n'.join(response.xpath("//body//text()").extract()).strip()
        title = ' '.join(response.xpath("//head/title//text()").extract()).strip()
    elif isinstance(response, TextResponse):
        text_data = response.text
    else:
        text_data = None

    # 20MB assuming 2 bytes per character, not the worst possible case for UTF-8 since some
    # characters encode as 4 bytes, but pretty safe based on normal text
    max_length = 10485760
    if text_data and len(text_data) > max_length:
        text_data = text_data[:max_length]

    return (title, text_data)


def is_processable(response):
    status_ok = response.status < 400 and response.status != 304
    is_cached = 'cached' in response.flags
    return status_ok and not is_cached
