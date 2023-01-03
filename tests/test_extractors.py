from searchbox.extractors import MicroformatExtractor, fix_url, is_github_html, compare_urls
from searchbox.extractors import get_links_from_markdown, get_text_from_markdown
from scrapy.http import TextResponse


def test_fix_url_missing_protocol():
    url = 'www.test.com'
    result = fix_url(url)
    assert result == 'http://www.test.com'


def test_can_detect_github_url():
    class Response(): pass
    response = Response()
    response.headers = {}
    
    response.headers['Content-Type'] = 'application/vnd.github.v3.html'.encode('utf-8')
    assert is_github_html(response)

    response.headers['Content-Type'] = 'application/json'.encode('utf-8')
    assert not is_github_html(response)


def test_can_compare_equivalent_urls():
    a = 'http://www.test.com/test/'
    b = 'http://www.test.com/test'
    assert compare_urls(a, b, ignore_protocol=False)


def test_can_compare_different_urls():
    a = 'http://www.test.com/test/'
    b = 'http://www.test.com2/test'
    assert not compare_urls(a, b, ignore_protocol=False)


def test_can_compare_equivalent_urls_ignoring_protocol():
    a = 'http://www.test.com/test/'
    b = 'ftp://www.test.com/test'
    assert compare_urls(a, b, ignore_protocol=True)


def test_can_compare_different_urls_ignoring_protocol():
    a = 'http://www.test.com/test/'
    b = 'http://www.test.com/test/?path=3'
    assert not compare_urls(a, b, ignore_protocol=True)


def test_can_extract_links_from_markdown():
    response = TextResponse(url='https://test.com')
    md = """
[Testing](/data/example.json)
# Section 1
Look at this:
[other](file:///dont_care_about_this.txt)
[](http://www.example2.com/testing?a=3&b=3)
"""
    links = list(get_links_from_markdown(response, md))
    assert len(links) == 2
    assert links[0] == 'https://test.com/data/example.json'
    assert links[1] == 'http://www.example2.com/testing?a=3&b=3'


def test_can_text_from_markdown():
    response = TextResponse(url='https://test.com')
    md = """
[Testing](/data/example.json)
# Section 1
Look at this:
[other](file:///dont_care_about_this.txt)
[](http://www.example2.com/testing?a=3&b=3)

Another piece of text
"""
    text = get_text_from_markdown(response, md)
    assert text == \
        'Testing  Section 1  Look at this: other   Another piece of text'


def test_can_extract_rdfa_tags():
    html: str = """<html>
<head>
<meta property='og:type' content='article' />
<meta property='article:tag' content='technology' />
<meta property='article:tag' content='oranges' />
</head>
<body>
<div vocab="http://schema.org/" typeof="Person">
<span>Hello</span>
</div>
</body>
</html>
    """

    extractor = MicroformatExtractor('https://rdfa.info/play/', html=html)
    tags = tuple(sorted(extractor.get_tags()))

    assert tags == ('oranges', 'technology')

