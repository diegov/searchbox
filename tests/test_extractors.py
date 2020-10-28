from searchbox.extractors import fix_url, is_github_html


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
