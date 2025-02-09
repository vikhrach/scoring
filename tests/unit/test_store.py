import store


def test_singleton():
    store1 = store.RedisStore()
    store2 = store.RedisStore()
    assert store1 is store2
