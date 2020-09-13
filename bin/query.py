#!/usr/bin/env python3
import sys
from elasticsearch import Elasticsearch
import dateutil.parser

INDEX_NAME = "scrapy"

def main():
    if len(sys.argv) < 2:
        sys.stderr.write('Usage: {} q QUERY TERMS\n'.format(sys.argv[0]))
        sys.exit(1)

    action = sys.argv[1]
    if action == 'q':
        query_terms = sys.argv[2:]
        run_query(query_terms)
    elif action == 'reset-index':
        run_reset_index()
    else:
        sys.stderr.write('Unknown action {}\n'.format(action))
        sys.exit(1)


def init_elastic() -> Elasticsearch:
    import os
    sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
    from searchbox import secrets_loader
    return Elasticsearch(hosts=[secrets_loader.get_elastic_authenticated_url()])


def run_query(query_terms):
    if len(query_terms) == 0:
        sys.stderr.write('No query provided\n')
        sys.exit(1)
    elif len(query_terms) == 1:
        query_term = query_terms[0]
    else:
        query_term = ' AND '.join('({})'.format(term) for term in query_terms)

    es = init_elastic()

    res = es.search(index=INDEX_NAME, body={
        "size": 30,
        "query": {
            "query_string": {
                "query": query_term,
                "fuzziness": "AUTO:2,6",
                "type": "best_fields"
            }
        }
    })

    print("Got %d Hits:" % res['hits']['total']['value'])
    for hit in res['hits']['hits']:
        item = hit['_source']

        def get_value(*keys):
            if len(keys) == 0: return ''
            key = keys[0]
            if key in item:
                value = item[key].strip() if item[key] else None
                if value:
                    return value.replace('\n', ' ')[:64].strip()
            return get_value(*keys[1:])

        name = get_value('name', 'description', 'content')

        print('({}) {}: {}'.format(year(item.get('last_update')), name, item['url']))


def year(dt) -> str:
    if dt is None:
        return '?'
    else:
        return str(dateutil.parser.isoparse(dt).year)


def run_reset_index():
    es: Elasticsearch = init_elastic()
    es.indices.delete(index=INDEX_NAME, ignore=[404])
    index_settings = {
        "settings": {
            "analysis" : {
                "analyzer" : {
                    "my_analyzer" : {
                        "tokenizer" : "standard",
                        "filter" : ["lowercase", "my_stemmer"]
                    }
                },
                "filter" : {
                    "my_stemmer" : {
                        "type" : "stemmer",
                        "name" : "light_english"
                    }
                }
            }
        }
    }
    es.indices.create(index=INDEX_NAME, body=index_settings)


if __name__ == '__main__':
    main()
