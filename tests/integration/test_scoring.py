def test_redis_connection(redis_cache):
    assert redis_cache.check()
