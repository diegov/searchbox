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
    
    if isinstance(response, HtmlResponse) or is_github_html(response):
        return ''.join(response.xpath("//body//text()").extract()).strip()
    elif isinstance(response, TextResponse):
        return response.text
    else:
        return None
