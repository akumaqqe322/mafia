from typing import Any

from app.infrastructure.redis import RedisClient


class FakeRedisRawClient:
    def __init__(self) -> None:
        self.data: dict[str, str | bytes] = {}
        self.sets: dict[str, set[str | bytes]] = {}

    async def set(
        self, key: str, value: str | bytes, **kwargs: Any
    ) -> str | bool | None:
        nx = kwargs.get("nx", False)
        if nx and key in self.data:
            return None
        self.data[key] = value
        return "OK"

    async def get(self, key: str) -> str | bytes | None:
        return self.data.get(key)

    async def delete(self, key: str) -> None:
        self.data.pop(key, None)
        self.sets.pop(key, None)

    async def exists(self, key: str) -> int:
        return 1 if key in self.data or key in self.sets else 0

    async def sadd(self, key: str, value: str | bytes) -> None:
        if key not in self.sets:
            self.sets[key] = set()
        val: str | bytes = (
            value.encode("utf-8") if isinstance(value, str) else value
        )
        self.sets[key].add(val)

    async def srem(self, key: str, value: str | bytes) -> None:
        if key in self.sets:
            val: str | bytes = (
                value.encode("utf-8") if isinstance(value, str) else value
            )
            self.sets[key].discard(val)

    async def smembers(self, key: str) -> set[str | bytes]:
        return self.sets.get(key, set())


class FakeRedisClient(RedisClient):
    def __init__(self) -> None:
        # We replace the client with our fake raw client
        self.client: Any = FakeRedisRawClient()

    async def check_connection(self) -> None:
        pass

    async def close(self) -> None:
        pass
