import pytest

import api
import store


@pytest.fixture
def method_handler(request):
    return api.method_handler({"body": request, "headers": {}}, {}, {})


@pytest.mark.parametrize(
    "account, login, method, token, arguments",
    [
        ("horns&hoofs", "h&f", "online_score", "", {}),
        ("horns&hoofs", "h&f", "online_score", "sdd", {}),
        ("horns&hoofs", "admin", "online_score", "", {}),
    ],
)
def test_bad_auth(account, login, method, token, arguments):
    request = {"account": account, "login": login, "method": method, "token": token, "arguments": arguments}
    _, code = api.method_handler({"body": request, "headers": {}}, {}, {})
    assert api.FORBIDDEN == code


@pytest.mark.parametrize(
    "arguments",
    [{"phone": "79175002040", "email": "stupnikov@otus.ru"}, {"phone": 79175002040, "email": "stupnikov@otus.ru"}],
)
def test_get_score_from_cache(set_valid_auth, arguments, mocker):
    request = {"account": "horns&hoofs", "login": "h&f", "method": "online_score", "arguments": arguments}
    set_valid_auth(request)
    store1 = store.RedisStore()
    mocker.patch.object(store1, "cache_get", return_value=43)
    response, code = api.method_handler({"body": request, "headers": {}}, {}, store1)
    assert response["score"] == 43
