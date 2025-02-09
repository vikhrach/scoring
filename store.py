import logging
import pickle
import threading
import time
from abc import ABC, abstractmethod

import redis


class Store(ABC):
    _instance = None
    _lock = threading.Lock()  # Lock to make it thread-safe

    def __new__(cls):
        with cls._lock:
            if not cls._instance:
                cls._instance = super(Store, cls).__new__(cls)
        return cls._instance

    @abstractmethod
    def get(self, key):
        """
        Retrieve the value associated with the given key from the store.
        """
        pass

    @abstractmethod
    def cache_get(self, key, cache_duration=60):
        """
        Attempt to get the value from the store. If not found or expired, fetch it and cache it.
        """
        pass

    @abstractmethod
    def cache_set(self, key, value, cache_duration=60):
        """
        Set a value in the store with an expiration time.
        """
        pass

    @abstractmethod
    def check(self):
        pass


class RedisStore(Store):
    def __init__(self, host="localhost", port=6379, db=0, socket_timeout=2, retry_delay=1, max_retries=2):
        # Initialize the Redis client
        self.host = host
        self.port = port
        self.db = db
        self.socket_timeout = socket_timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay  # Delay between retries in seconds
        self.connect()

    def get(self, key):
        """
        Retrieve the value from Redis.
        If the key is not found, return None.
        """
        if self.check():
            value = self.client.get(key)
            if value:
                # Deserialize the value before returning
                return pickle.loads(value)
        return None

    def cache_get(self, key):
        """
        Attempt to get the value from Redis. If the value is not found or expired,
        cache the value for the given duration (in seconds).
        """
        value = self.get(key)
        return value

    def cache_set(self, key, value, cache_duration=60):
        """
        Set a value in Redis with an optional expiration time.
        """
        if self.check():
            serialized_value = pickle.dumps(value)
            self.client.setex(key, cache_duration, serialized_value)

    def connect(self):
        self.client = redis.StrictRedis(host=self.host, port=self.port, db=self.db, socket_timeout=self.socket_timeout)

    def check(self):
        attempt = 0
        while attempt < self.max_retries:
            try:
                # Test the connection
                self.client.ping()
                logging.info("connection try")
                return True
            except redis.TimeoutError as e:
                attempt += 1
                logging.info(f"Connection attempt {attempt} failed: {e}")
                logging.info(f"Retrying in {self.retry_delay} seconds...")
                time.sleep(self.retry_delay)
                self.connect()
            return False
