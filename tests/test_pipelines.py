from typing import Any
from searchbox.items import CrawlItem
from searchbox.pipelines import ConvertToItemPipeline


def test_when_converting_to_scrapy_item_empty_values_should_be_ignored():
    pipeline = ConvertToItemPipeline()

    item = CrawlItem(name='testing', description='test item', twitter_tags=['a', 'b', 'c'])
    result = pipeline.process_item(item, Any)
    assert sorted(result.field_names()) == ['description', 'name', 'twitter_tags']

    item = CrawlItem(name='testing', alt_url="http://test.example.com/test")
    result = pipeline.process_item(item, Any)
    assert sorted(result.field_names()) == ['alt_url', 'name']
