from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, cast

import pytest

from magmatic import ConsumptionQueue, LoopType, Queue, Track, WaitableConsumptionQueue, WaitableQueue
from magmatic.errors import QueueFull

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


def test_queue_up_next() -> None:
    queue = Queue()

    first = cast(Track, 1)
    second = cast(Track, 2)

    queue.add_multiple((first, second))

    assert queue.up_next == 1
    queue.get()
    assert queue.up_next == 2
    queue.get()
    assert queue.up_next is None


def test_queue_add_discard() -> None:
    queue = Queue(max_size=1)

    first = cast(Track, 1)
    second = cast(Track, 2)

    queue.add(first)
    discarded = queue.add(second, discard=True)

    assert discarded == [1]
    assert queue.get() == 2
    assert len(queue) == 1


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

    assert len(queue) == 1


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

    result = await asyncio.wait_for(queue.get_wait(), timeout=0.5)
    assert result == 1

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(queue.get_wait(), timeout=0.5)


@pytest.mark.asyncio
async def test_waitable_consumption_queue(event_loop: AbstractEventLoop) -> None:
    queue = WaitableConsumptionQueue(loop=event_loop)

    first = cast(Track, 1)
    queue.add(first)

    result = await asyncio.wait_for(queue.get_wait(), timeout=0.5)
    assert result == 1
    assert len(queue) == 0
