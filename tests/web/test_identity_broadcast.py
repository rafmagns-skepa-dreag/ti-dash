import asyncio
import pytest
from ti_dash.web.identity import new_device_id, DEVICE_COOKIE, ADMIN_COOKIE
from ti_dash.web.broadcast import Broadcaster


def test_device_ids_are_unique_hex():
    a, b = new_device_id(), new_device_id()
    assert a != b and len(a) >= 16
    assert DEVICE_COOKIE == "device_id" and ADMIN_COOKIE == "is_admin"


async def test_publish_reaches_all_subscribers():
    b = Broadcaster()
    q1, q2 = b.subscribe(), b.subscribe()
    assert b.count == 2
    await b.publish("hello")
    assert await asyncio.wait_for(q1.get(), 1) == "hello"
    assert await asyncio.wait_for(q2.get(), 1) == "hello"


async def test_unsubscribe_removes_queue():
    b = Broadcaster()
    q = b.subscribe()
    b.unsubscribe(q)
    assert b.count == 0
    await b.publish("x")  # no error with zero subscribers
