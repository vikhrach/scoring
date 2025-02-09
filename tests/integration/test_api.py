import datetime

import pytest
import requests

from scoring import api, store


@pytest.mark.parametrize(
    "account, login, method, token, arguments",
    [
        ("horns&hoofs", "h&f", "online_score", "", {}),
        ("horns&hoofs", "h&f", "online_score", "sdd", {}),
        ("horns&hoofs", "admin", "online_score", "", {}),
    ],
)
def test_server_response(get_url, account, login, method, token, arguments):
    request = {"account": account, "login": login, "method": method, "token": token, "arguments": arguments}
    r = requests.post(get_url + "/method", json=request)
    assert r.status_code == api.FORBIDDEN


@pytest.mark.parametrize(
    "arguments",
    [{"phone": "79175002040", "email": "stupnikov@otus.ru"}, {"phone": 79175002040, "email": "stupnikov@otus.ru"}],
)
def test_ok_online_score(get_url, set_valid_auth, arguments):
    request = {"account": "horns&hoofs", "login": "h&f", "method": "online_score", "arguments": arguments}
    set_valid_auth(request)
    r = requests.post(get_url + "/method", json=request)
    assert r.status_code == api.OK


@pytest.mark.parametrize(
    "arguments",
    [
        {"client_ids": [0], "date": datetime.datetime.today().strftime("%d.%m.%Y")},
        {"client_ids": [0], "date": "19.07.2017"},
    ],
)
def test_ok_interests_request(get_url, set_valid_auth, arguments):
    request = {"account": "horns&hoofs", "login": "h&f", "method": "clients_interests", "arguments": arguments}
    set_valid_auth(request)
    testStore = store.RedisStore()
    testStore.cache_set("i:0", b'["a","b"]')
    r = requests.post(get_url + "/method", json=request)
    assert r.status_code == api.OK


@pytest.mark.parametrize(
    "arguments",
    [
        {"client_ids": [1], "date": datetime.datetime.today().strftime("%d.%m.%Y")},
        {"client_ids": [1], "date": "19.07.2017"},
    ],
)
def test_interests_request_no_value_in_cache(get_url, set_valid_auth, arguments):
    request = {"account": "horns&hoofs", "login": "h&f", "method": "clients_interests", "arguments": arguments}
    set_valid_auth(request)
    r = requests.post(get_url + "/method", json=request)
    assert r.status_code == api.INVALID_REQUEST
