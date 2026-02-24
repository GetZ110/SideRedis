"""Thread-safe async Redis connection manager - simplified version.

Uses simple threading for all operations to avoid event loop issues.
"""

from __future__ import annotations

import concurrent.futures
import threading
from typing import Any

import redis


class ThreadSafeRedisManager:
    """Manages Redis connections with ThreadPoolExecutor for non-blocking operations."""

    def __init__(self) -> None:
        self._client: redis.Redis | None = None
        self._raw_client: redis.Redis | None = None
        self._executor: concurrent.futures.ThreadPoolExecutor | None = None
        self._lock = threading.Lock()

        # Connection info
        self.host: str = "localhost"
        self.port: int = 6379
        self.db: int = 0
        self.password: str = ""
        self.username: str = ""

    @property
    def connected(self) -> bool:
        """Check if connected to Redis."""
        return self._client is not None

    @property
    def client(self) -> redis.Redis:
        """Get the text-decoding Redis client."""
        if self._client is None:
            raise ConnectionError("Not connected to Redis")
        return self._client

    @property
    def raw_client(self) -> redis.Redis:
        """Get the raw bytes Redis client."""
        if self._raw_client is None:
            raise ConnectionError("Not connected to Redis")
        return self._raw_client

    def connect(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: str = "",
        username: str = "",
    ) -> None:
        """Connect to Redis server synchronously."""
        # First, try to connect with a temporary client to verify connection
        test_common = {
            "host": host,
            "port": port,
            "db": db,
            "password": password or None,
            "username": username or None,
            "socket_connect_timeout": 5,
            "socket_timeout": 10,
            "decode_responses": True,
        }

        # Test connection
        test_client = redis.Redis(**test_common)
        try:
            test_client.ping()
        except Exception as e:
            raise ConnectionError(f"Failed to connect to {host}:{port}: {e}")
        finally:
            test_client.close()

        # If connection succeeded, create the actual clients
        with self._lock:
            # Direct cleanup without calling disconnect() to avoid deadlock
            if self._client:
                try:
                    self._client.close()
                except Exception:
                    pass
            if self._raw_client:
                try:
                    self._raw_client.close()
                except Exception:
                    pass
            if self._executor:
                try:
                    self._executor.shutdown(wait=False)
                except Exception:
                    pass

            self.host = host
            self.port = port
            self.db = db
            self.password = password
            self.username = username

            # Create clients
            common = {
                "host": host,
                "port": port,
                "db": db,
                "password": password or None,
                "username": username or None,
                "socket_connect_timeout": 5,
                "socket_timeout": 10,
                "decode_responses": True,
                "health_check_interval": 30,
            }

            self._client = redis.Redis(**common)
            self._raw_client = redis.Redis(**{**common, "decode_responses": False})

        # Initialize thread pool after releasing lock
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=4, thread_name_prefix="redis_worker"
        )

    def disconnect(self) -> None:
        """Disconnect from Redis and cleanup."""
        with self._lock:
            if self._client:
                try:
                    self._client.close()
                except Exception:
                    pass
            if self._raw_client:
                try:
                    self._raw_client.close()
                except Exception:
                    pass
            if self._executor:
                self._executor.shutdown(wait=False)
                self._executor = None
            self._client = None
            self._raw_client = None

    def select_db(self, db: int) -> None:
        """Select a different database."""
        with self._lock:
            if self._client:
                self._client.select(db)
            if self._raw_client:
                self._raw_client.select(db)
            self.db = db

    def execute(self, func, *args, **kwargs) -> Any:
        """Execute a Redis command in the thread pool."""
        if self._executor is None:
            raise ConnectionError("Not connected to Redis")
        return self._executor.submit(func, *args, **kwargs).result(timeout=30)

    # ---- Key Operations ----

    def scan_keys(self, pattern: str = "*", count: int = 100, cursor: int = 0):
        """Scan for keys matching pattern."""
        return self.execute(self.client.scan, cursor=cursor, match=pattern, count=count)

    def get_db_size(self) -> int:
        """Get database size."""
        return self.execute(self.client.dbsize)

    def get_key_type(self, key: str) -> str:
        """Get key type."""
        return self.execute(self.client.type, key)

    def get_key_value(self, key: str):
        """Get key value and type."""
        key_type = self.execute(self.client.type, key)
        if key_type == "string":
            value = self.execute(self.client.get, key)
        elif key_type == "hash":
            value = self.execute(self.client.hgetall, key)
        elif key_type == "list":
            value = self.execute(self.client.lrange, key, 0, -1)
        elif key_type == "set":
            value = list(self.execute(self.client.smembers, key))
        elif key_type == "zset":
            value = self.execute(self.client.zrange, key, 0, -1, withscores=True)
        elif key_type == "stream":
            value = self.execute(self.client.xrange, key, count=100)
        else:
            value = None
        return key_type, value

    def get_ttl(self, key: str) -> int:
        """Get key TTL."""
        return self.execute(self.client.ttl, key)

    def set_ttl(self, key: str, ttl: int) -> None:
        """Set key TTL."""
        self.execute(self.client.expire, key, ttl)

    def rename_key(self, key: str, new_key: str) -> None:
        """Rename a key."""
        self.execute(self.client.rename, key, new_key)

    def delete_keys(self, *keys: str) -> int:
        """Delete keys."""
        return self.execute(self.client.delete, *keys)

    def set_key_value(self, key: str, value: str) -> None:
        """Set string value."""
        self.execute(self.client.set, key, value)

    def get_server_info(self) -> dict:
        """Get server info."""
        return self.execute(self.client.info)


# Global instance
redis_manager = ThreadSafeRedisManager()
