from searchbox.extractors import fix_url, is_github_html, compare_urls


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
