#!/usr/bin/env python3
import sys
from elasticsearch import Elasticsearch
import dateutil.parser
from statistics import stdev, mean


INDEX_NAME = "scrapy"

MAX_TITLE_LEN = 54

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

    res = es.search(index=INDEX_NAME, size=30, query={
        "query_string": {
            "query": query_term,
            "fuzziness": "AUTO:2,6",
            "type": "best_fields"
        }
    })

    # TODO: There's probably some corpus-wide value we could get from ES instead of doing this
    # for just 30 results.
    scores = [i['_score'] for i in res['hits']['hits']]

    if scores:
        mu = mean(scores)
    else:
        mu = 0.0

    if len(scores) > 1:
        deviation = stdev(scores, xbar=mu)
    else:
        deviation = 0.0

    good_score = mu + deviation

    print("Got %d Hits:" % res['hits']['total']['value'])
    for hit in reversed(res['hits']['hits']):
        item = hit['_source']
        score = hit['_score']

        def get_value(*keys):
            if len(keys) == 0: return ''
            key = keys[0]
            if key in item:
                value = item[key].strip() if item[key] else None
                if value:
                    return value.replace('\n', ' ')[:64].strip()
            return get_value(*keys[1:])

        def get_title_value(*keys, base_value=None) -> str:
            if len(keys) == 0 or (base_value and len(base_value) >= MAX_TITLE_LEN):
                return make_title(base_value or '')

            key = keys[0]
            current = [base_value] if base_value else []
            if key in item:
                value = item[key].strip() if item[key] else None
                if value:
                    clean_value = value.replace('\n', ' ')[:64].strip()
                    current += [clean_value]
            return get_title_value(*keys[1:], base_value=' - '.join(current))

        name = get_title_value('name', 'description', 'content')

        if score >= good_score:
            icon = '★'
        else:
            icon = ''

        print('({}) {:3.1f}{} {}: {}'.format(year(
            get_value('last_update', 'article_published_date')),
                                             score, icon, name, item['url']))


def make_title(title: str) -> str:
    max_len = MAX_TITLE_LEN
    if len(title) <= max_len:
        return title

    parts = title.split(' ')
    result = []
    total_len = 0

    for i in range(len(parts)):
        part = parts[i]
        clean = part.strip()

        if not clean:
            continue

        new_len = total_len + len(clean)
        sep_len = 1 if result else 0

        if new_len + sep_len > max_len:
            result[-1] = result[-1] + '…'
            break

        result.append(clean)
        total_len = new_len + sep_len

    return ' '.join(result)


def year(dt) -> str:
    if not dt:
        return '?'

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
