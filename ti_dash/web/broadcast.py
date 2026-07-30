import asyncio


class Broadcaster:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[str]] = set()

    def subscribe(self) -> asyncio.Queue[str]:
        q: asyncio.Queue[str] = asyncio.Queue()
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[str]) -> None:
        self._subscribers.discard(q)

    async def publish(self, payload: str) -> None:
        for q in list(self._subscribers):
            await q.put(payload)

    @property
    def count(self) -> int:
        return len(self._subscribers)
