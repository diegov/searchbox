Intro
======

Simple crawling and indexing of personal bookmarks with Elasticsearch backend. 
Both indexing and search are WIP and need lots of work.

Sources: 

- [x] Github stars
- [x] Pocket bookmarks
- [ ] Saved Reddit posts
- [X] Liked tweets

Configuration
==============

The application expects a `~/.config/searchbox/secrets.py` file, with the following structure:

```python

github = {
    # Users whose stars will be crawled
    "users_to_crawl": ["user1"],
    # Username for API access
    "username": "apiuser1",
    "personal_access_token": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
}

pocket = {
    "consumer_key": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "access_token": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
}

elastic = {
    "url": "https://xxxxxxxx",
    # Optional
    "username": "xxxxxxx",
    # Optional
    "password": "xxxxxxx"
}

```

The `elastic` section is required, `github` or `pocket` can be omitted if the specific spider won't be used. 

Unfortunately each service requires its own type of API access, registering app keys, OAuth, etc... so:

Pocket
-------

It requires an application to be registered in https://getpocket.com/developer/apps/, which will give you the `consumer_key`. 
After that we've to do the OAuh dance as specified in https://getpocket.com/developer/docs/authentication, which will result in an authenticated `access_token`.

Github
-------

This is much simpler, see https://help.github.com/en/github/authenticating-to-github/creating-a-personal-access-token-for-the-command-line

Elastic
--------

See the details from your Elasticsearch provider, local deployment, container, etc...

If the Elasticsearch configuration does not automatically create indexes, you'll need to create one called `scrapy` before indexing.

Running
========

From the root of the project
```sh
python3 -m venv venv
. venv/bin/activate
pip install -r requirements.txt
bin/crawl
```

There are two spiders, `github_stars` and `pocket`. `crawl` is a shell script that will run both, but they can be run individually instead, eg:
```sh
scrapy crawl github_stars
```

At the end of this some data should be stored in Elasticsearch. There's a simple test script that will query the results

```sh
bin/query q python
```

Will return the first 30 results matching `python`.

```sh
bin/query q python performance
```

Will return the first 30 results matching `python` AND `performance`.


```sh
bin/query reset-index
```

Will delete all the data in the elastic index, and re-create the index.
