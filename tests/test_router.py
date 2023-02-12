import unittest

from scrapy.http import Request

from searchbox.router import Router
from searchbox.types import SpiderRequests, SpiderResults

from unittest import mock


class RouterTest(unittest.TestCase):
    def setUp(self):
        self.sut = Router()
        self.process_spider = mock.MagicMock()
        self.process_spider2 = mock.MagicMock()
        self.request_spider = mock.MagicMock()

    @staticmethod
    def ignore1(_: Request) -> SpiderResults:
        return
        yield

    @staticmethod
    def ignore2(_: Request) -> SpiderResults:
        return
        yield

    def test_if_url_matcher_doesnt_replace_it_should_return_original(self):
        def do_nothing(_: Request) -> SpiderRequests:
            return
            yield

        self.sut.matchers.append((self.process_spider, do_nothing))

        r = Request("http://example.com", callback=RouterTest.ignore1)

        result = list(self.sut.process_request(self.request_spider, r))
        self.assertListEqual(result, [r])

    def test_if_url_matcher_replaces_it_should_not_return_original(self):
        def replace_request(_: Request) -> SpiderRequests:
            yield Request("http://different.example.com/2", callback=RouterTest.ignore2)
            yield Request("http://different.example.com/3", callback=RouterTest.ignore2)

        self.sut.matchers.append((self.process_spider, replace_request))

        r = Request("http://example.com", callback=RouterTest.ignore1)

        result = list(self.sut.process_request(self.request_spider, r))
        self.assertListEqual(
            [r.url for r in result],
            ["http://different.example.com/2", "http://different.example.com/3"],
        )

        for req in result:
            self.assertEqual(req.callback, RouterTest.ignore2)

    def test_if_multiple_matchers_match_it_should_return_the_first_matchers_results(
        self,
    ):
        def replace_request1(_: Request) -> SpiderRequests:
            yield Request(
                "http://different.example.com/first", callback=RouterTest.ignore1
            )

        self.sut.matchers.append((self.process_spider, replace_request1))

        def replace_request2(_: Request) -> SpiderRequests:
            yield Request(
                "http://different.example.com/second", callback=RouterTest.ignore1
            )
            yield Request(
                "http://different.example.com/more_second", callback=RouterTest.ignore1
            )

        self.sut.matchers.append((self.process_spider2, replace_request2))

        r = Request("http://example.com", callback=RouterTest.ignore1)

        result = list(self.sut.process_request(self.request_spider, r))
        self.assertListEqual(
            [r.url for r in result], ["http://different.example.com/first"]
        )

    def test_when_replacing_it_should_merge_metadata(self):
        def replace_request(_: Request) -> SpiderRequests:
            new_req = Request(
                "http://different.example.com/2", callback=RouterTest.ignore1
            )
            new_req.meta["new_data"] = 10
            new_req.meta["old_data2"] = 7
            yield new_req

        self.sut.matchers.append((self.process_spider, replace_request))

        r = Request("http://example.com", callback=RouterTest.ignore1)
        r.meta["old_data1"] = 5
        r.meta["old_data2"] = 6

        result = list(self.sut.process_request(self.request_spider, r))
        self.assertListEqual(
            [r.url for r in result], ["http://different.example.com/2"]
        )
        self.assertDictEqual(
            result[0].meta, {"old_data1": 5, "old_data2": 7, "new_data": 10}
        )

    def test_if_the_request_is_by_the_same_spider_it_should_not_replace_it(self):
        def replace_request1(_: Request) -> SpiderRequests:
            yield Request(
                "http://different.example.com/first", callback=RouterTest.ignore1
            )

        self.sut.matchers.append((self.process_spider, replace_request1))

        def replace_request2(_: Request) -> SpiderRequests:
            yield Request(
                "http://different.example.com/second", callback=RouterTest.ignore1
            )
            yield Request(
                "http://different.example.com/more_second", callback=RouterTest.ignore1
            )

        self.sut.matchers.append((self.process_spider2, replace_request2))

        r = Request("http://example.com", callback=RouterTest.ignore1)

        result = list(self.sut.process_request(self.process_spider, r))
        self.assertListEqual(
            [r.url for r in result],
            [
                "http://different.example.com/second",
                "http://different.example.com/more_second",
            ],
        )
