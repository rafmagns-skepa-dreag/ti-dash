import asyncio


class Broadcaster:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[str | None]] = set()

    def subscribe(self) -> asyncio.Queue[str | None]:
        q: asyncio.Queue[str | None] = asyncio.Queue()
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[str | None]) -> None:
        self._subscribers.discard(q)

    async def publish(self, payload: str) -> None:
        for q in list(self._subscribers):
            await q.put(payload)

    async def close_all(self) -> None:
        """Unblock every subscriber's queue.get() with a sentinel so their SSE
        stream can return and the connection close during shutdown, instead of
        hanging on a queue that will never receive another item."""
        for q in list(self._subscribers):
            await q.put(None)

    @property
    def count(self) -> int:
        return len(self._subscribers)
