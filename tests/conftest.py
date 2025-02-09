import datetime
import hashlib
import logging

import pytest

import api
import store

logging.basicConfig(
    # filename=args.log,
    level=logging.INFO,
    format="[%(asctime)s] %(levelname).1s %(message)s",
    datefmt="%Y.%m.%d %H:%M:%S",
    handlers=[logging.StreamHandler()],
)


@pytest.fixture
def redis_cache():
    print("resi")
    return store.RedisStore()


@pytest.fixture
def get_url():
    return "http://localhost:8080"


@pytest.fixture
def set_valid_auth():
    def set_token(request):
        if request.get("login") == api.ADMIN_LOGIN:
            request["token"] = hashlib.sha512(
                (datetime.datetime.today().strftime("%Y%m%d%H") + api.ADMIN_SALT).encode("utf-8")
            ).hexdigest()
        else:
            msg = (request.get("account", "") + request.get("login", "") + api.SALT).encode("utf-8")
            request["token"] = hashlib.sha512(msg).hexdigest()

    return set_token
