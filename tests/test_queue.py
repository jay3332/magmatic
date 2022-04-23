from __future__ import annotations

from typing import TYPE_CHECKING, cast

from magmatic import ConsumptionQueue, Queue, WaitableQueue, Track, LoopType
from magmatic.errors import QueueFull
import pytest

if TYPE_CHECKING:
    from asyncio import AbstractEventLoop


def test_queue_add_get() -> None:
    queue = Queue()

    first = cast(Track, 1)
    second = cast(Track, 2)
    third = cast(Track, 3)

    queue.add(first)
    queue.add(second)
    queue.add(third)
    assert queue.get() == 1
    assert queue.get() == 2
    assert queue.get() == 3
    assert queue.get() is None

def test_queue_loop_queue() -> None:
    queue = Queue(loop_type=LoopType.queue)

    first = cast(Track, 1)
    second = cast(Track, 2)

    queue.add(first)
    queue.add(second)

    assert queue.get() == 1
    assert queue.get() == 2
    assert queue.get() == 1
    assert queue.get() == 2

def test_queue_loop_track() -> None:
    queue = Queue(loop_type=LoopType.track)

    first = cast(Track, 1)

    queue.add(first)

    assert queue.get() == 1
    assert queue.get() == 1

def test_queue_max_size() -> None:
    queue = Queue(max_size=1)

    first = cast(Track, 1)

    queue.add(first)

    with pytest.raises(QueueFull):
        queue.add(first)

def test_consumption_queue() -> None:
    queue = ConsumptionQueue()

    first = cast(Track, 1)

    queue.add(first)
    queue.get()
    
    assert len(queue) == 0

@pytest.mark.asyncio
async def test_waitable_queue(event_loop: AbstractEventLoop) -> None:
    queue = WaitableQueue(loop=event_loop)

    first = cast(Track, 1)

    queue.add(first)

    assert await queue.get_wait() == 1
