import os
from os.path import expanduser
from urllib.parse import urlparse, ParseResult
import importlib.util
from importlib.abc import Loader

home = expanduser("~")
secrets_path = os.path.abspath(os.path.join(home, '.config/searchbox/secrets.py'))
spec = importlib.util.spec_from_file_location(secrets_path, secrets_path)
if spec is None:
    raise Exception('Can\'t find module at path {}'.format(secrets_path))

secrets = importlib.util.module_from_spec(spec)
assert secrets is not None

assert isinstance(spec.loader, Loader) 
spec.loader.exec_module(secrets)

SECRETS = secrets

def get_elastic_authenticated_url():
    conn_params = SECRETS.elastic
    url = conn_params['url']
    
    if 'username' in conn_params and conn_params['username']:
        url_parts = urlparse(url)
        authenticated_url = ParseResult(scheme=url_parts.scheme, netloc='{}:{}@{}'.format(conn_params['username'], conn_params['password'], url_parts.netloc),
                                        path=url_parts.path, params=url_parts.params, query=url_parts.query, fragment=url_parts.fragment)

        return authenticated_url.geturl()
    else:
        return url
