#!/usr/bin/env python3

from elasticsearch import Elasticsearch

INDEX_NAME = "scrapy"

def main():
    import sys

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
    import sys
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
                "fuzziness": 5,
                "type": "most_fields"
            }
        }
    })

    print("Got %d Hits:" % res['hits']['total']['value'])
    for hit in res['hits']['hits']:
        item = hit['_source']
        if 'name' in item:
            print('{}: {}'.format(item['name'], item['url']))


def run_reset_index():
    es: Elasticsearch = init_elastic()
    es.indices.delete(index=INDEX_NAME, ignore=[404])
    es.indices.create(index=INDEX_NAME)


if __name__ == '__main__':
    main()
