from __future__ import annotations

import asyncio
from abc import ABC
from collections import deque
from enum import IntEnum
from functools import wraps
from typing import (
    Any,
    AsyncIterator,
    Callable,
    Generic,
    Iterable,
    Iterator,
    List,
    Optional,
    Protocol,
    TYPE_CHECKING,
    Type,
    TypeVar,
    Union,
)

from .errors import QueueFull
from .track import Playlist, Track

MetadataT = TypeVar('MetadataT')

if TYPE_CHECKING:
    from typing_extensions import ParamSpec

    Enqueueable = Union[Track[MetadataT], Playlist[MetadataT]]

    P = ParamSpec('P')
    R = TypeVar('R')

    # PyCharm does not support typing[_extensions].Self
    _IT = TypeVar('_IT', bound='_InternalQueue')
    BaseQueueT = TypeVar('BaseQueueT', bound='BaseQueue')
    ConsumptionQueueT = TypeVar('ConsumptionQueueT', bound='ConsumptionQueue')
    QueueT = TypeVar('QueueT', bound='Queue')

    class _InternalQueue(Protocol[MetadataT]):
        def __getitem__(self, index: int, /) -> Track[MetadataT]: ...
        def __setitem__(self, index: int, value: Track[MetadataT], /) -> None: ...
        def __delitem__(self, index: int, /) -> None: ...
        def __len__(self) -> int: ...
        def __iter__(self) -> Iterator[Track[MetadataT]]: ...
        def __contains__(self, item: Track[MetadataT], /) -> bool: ...
        def __reversed__(self) -> Iterator[Track[MetadataT]]: ...
        def append(self, value: Track[MetadataT], /) -> None: ...
        def extend(self, values: Iterable[Track[MetadataT]], /) -> None: ...
        def insert(self, index: int, value: Track[MetadataT], /) -> None: ...
        def reverse(self) -> None: ...
        def pop(self) -> Track[MetadataT]: ...
        def popleft(self) -> Track[MetadataT]: ...
        def remove(self, value: Track[MetadataT], /) -> None: ...
        def clear(self) -> None: ...
        def copy(self: _IT) -> _IT: ...

__all__ = (
    'BaseQueue',
    'ConsumptionQueue',
    'LoopType',
    'Queue',
    'WaitableConsumptionQueue',
    'WaitableQueue',
)


class BaseQueue(Iterable[Track[MetadataT]], Generic[MetadataT], ABC):
    """An abstract base class that all queues should inherit from.

    In reality, this wraps over an internal queue, i.e. a :py:class:`deque` by default.

    Attributes
    ----------
    max_size: int
        The maximum size of the queue. ``None`` if no maximum size was set.
    """

    __slots__ = ()

    max_size: Optional[int]
    _queue: _InternalQueue[MetadataT]

    @property
    def count(self) -> int:
        """int: The number of tracks in the queue."""
        return len(self._queue)

    @property
    def queue(self) -> _InternalQueue[MetadataT]:
        """The internal queue this queue wraps around. Usually :py:class:`~collections.deque`."""
        return self._queue

    @property
    def current(self) -> Optional[Track[MetadataT]]:
        """Optional[:class:`.Track`]: The current track the queue is pointing to.

        This is ``None`` if the queue is empty or if the queue is not pointing to a track.
        """
        raise NotImplementedError

    @property
    def up_next(self) -> Optional[Track[MetadataT]]:
        """Optional[:class:`.Track`]: The next track in the queue.
        This is ``None`` if there is no next track.
        """
        raise NotImplementedError

    @property
    def upcoming(self) -> List[Track[MetadataT]]:
        """List[:class:`.Track`]: A list of all upcoming tracks in the queue."""
        raise NotImplementedError

    def is_empty(self) -> bool:
        """bool: Whether the queue is empty."""
        return not self

    def is_full(self) -> bool:
        """bool: Whether the queue is full. This is always ``False`` for queues that do not have a maximum size."""
        return self.max_size is not None and self.count >= self.max_size

    def _get(self) -> Optional[Track[MetadataT]]:
        raise NotImplementedError

    def _skip(self) -> Optional[Track[MetadataT]]:
        return self._get()

    def _add(self, track: Track[MetadataT]) -> None:
        self._queue.append(track)

    def _insert(self, index: int, track: Track[MetadataT]) -> None:
        self._queue.insert(index, track)

    def _free(self) -> Track[MetadataT]:
        return self._queue.pop()

    def get(self) -> Optional[Track[MetadataT]]:
        """Gets the next track in the queue. If no tracks are in the queue, this returns ``None``.

        Returns
        -------
        Optional[Track[MetadataT]]
            The next track in the queue, or ``None`` if the queue is empty.
        """
        return None if self.is_empty() else self._get()

    def pop(self) -> Optional[Track[MetadataT]]:
        """Pops the last enqueued track from the queue. If no tracks are in the queue, this returns ``None``.

        Returns
        -------
        Optional[Track[MetadataT]]
            The next track in the queue, or ``None`` if the queue is empty.
        """
        return None if self.is_empty() else self._free()

    def add(self, item: Enqueueable[MetadataT], *, discard: bool = False) -> List[Track[MetadataT]]:  # type: ignore
        """Adds/enqueues a track or playlist to the queue.

        If a playlist is provided, each of its tracks will be added to the queue.

        Parameters
        ----------
        item: Union[:class:`Track`, :class:`Playlist`]
            The track or playlist to add to the queue.
        discard: bool
            Whether to discard another track if the queue is full.
            If this is ``False`` (the default), :exception:`QueueFull` will be raised instead.

        Returns
        -------
        List[:class:`Track`]
            A list of discarded tracks if ``discard`` was ``True``.
            If ``discard`` was ``False``, this will be an empty list.

        Raises
        ------
        QueueFull
            If the queue is full and ``discard`` was ``False``.
        """
        tracks = item.tracks if isinstance(item, Playlist) else (item,)
        discarded = []

        for track in tracks:
            if self.is_full():
                if discard:
                    discarded.append(self._free())
                else:
                    raise QueueFull(self, track)

            self._add(track)

        return discarded

    def add_multiple(self, items: Iterable[Enqueueable[MetadataT]], *, discard: bool = False) -> List[Track[MetadataT]]:  # type: ignore
        """Adds multiple tracks or playlists to the queue.

        This is in reality just a shortcut to calling :meth:`add` for each track or playlist in the iterable.

        Parameters
        ----------
        items: Iterable[Union[:class:`Track`, :class:`Playlist`]]
            An iterable (i.e. a :py:class:`list`) of tracks or playlists to add to the queue.
        discard: bool
            Whether to discard another track if the queue is full.
            If this is ``False`` (the default), :exception:`QueueFull` will be raised instead.

        Returns
        -------
        List[:class:`Track`]
            A list of discarded tracks if ``discard`` was ``True``.
            If ``discard`` was ``False``, this will be an empty list.

        Raises
        ------
        QueueFull
            If the queue is full and ``discard`` was ``False``.
        """
        # We choose to do it this way because sum is slow for this type of operation.
        discarded = []

        for item in items:
            discarded += self.add(item, discard=discard)

        return discarded

    def extend(self, items: Iterable[Enqueueable[MetadataT]], *, discard: bool = False) -> List[Track[MetadataT]]:  # type: ignore
        """An alias for :meth:`add_multiple`. See documentation for that instead."""
        return self.add_multiple(items, discard=discard)

    def remove_index(self, index: int = 0) -> Track[MetadataT]:
        """Removes the track at the specified index from the queue.
        If you have an index, this is usually preferred over :meth:`remove`.

        .. note::
            This is zero-indexed - the first track is at index ``0``.

        Parameters
        ----------
        index: int
            The index of the track to removed.

        Returns
        -------
        :class:`Track`
            The track that was removed.
        """
        if index < 0:
            index += len(self)

        if index < 0 or index >= len(self):
            raise IndexError(f'index {index} out of range')

        if index == 0:
            return self._queue.popleft()

        elif index - 1 == len(self):
            return self._queue.pop()

        track = self._queue[index]
        del self._queue[index]
        return track

    def remove(self, item: Track[MetadataT]) -> None:
        """Removes a track (or track at a given index) from the queue.

        Parameters
        ----------
        item: :class:`Track`
            The track to remove from the queue, or the index of the track to remove.
        """
        self._queue.remove(item)

    def skip(self, count: int = 1) -> Optional[Track[MetadataT]]:
        """Skips the next track (or ``count`` number of tracks) in the queue and returns the new track.
        In some queue implementations, this is identical to :meth:`get`.

        In :class:`.Queue`, this will ignore :attr:`.LoopType.track` and move on to the next track
        regardless.

        Parameters
        ----------
        count: int
            The number of tracks to skip. Defaults to ``1``.

        Returns
        -------
        Optional[:class:`Track`]
            The retrieved track, or ``None`` if the queue is empty.
        """
        if self.is_empty():
            return None

        for _ in range(count - 1):
            self._skip()

        return self._skip()

    def insert(self, index: int, item: Enqueueable[MetadataT]) -> None:    # type: ignore
        """Inserts a track or playlist into the queue at the specified index.

        .. note::
            This is zero-indexed - the first track is at index ``0``.

        Parameters
        ----------
        index: int
            The index at which to insert the track or playlist.
        item: Union[:class:`Track`, :class:`Playlist`]
            The track or playlist to insert.
        """
        tracks = item.tracks if isinstance(item, Playlist) else (item,)

        for i, track in enumerate(tracks):
            self._insert(index + i, track)

    def jump_to(self, index: int) -> Track[MetadataT]:
        """Jumps to the track at the given index.

        .. note::
            This is zero-indexed - the first track is at index ``0``.

        Parameters
        ----------
        index: :class:`int`
            The index to jump to.

        Returns
        -------
        :class:`.Track`
            The track at the given index.
        """
        raise NotImplementedError

    def jump_to_last(self) -> Track[MetadataT]:
        """Jumps to the last track in the queue.

        Returns
        -------
        :class:`.Track`
            The last track in the queue.
        """
        return self.jump_to(len(self) - 1)

    def clear(self) -> None:
        """Removes all tracks from the queue."""
        self._queue.clear()

    def copy(self: BaseQueueT) -> BaseQueueT:
        """Creates and returns a copy of the queue."""
        raise NotImplementedError

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__} count={self.count}>'

    def __bool__(self) -> bool:
        return bool(self.count)

    def __copy__(self: BaseQueueT) -> BaseQueueT:
        return self.copy()

    def __len__(self) -> int:
        return self.count

    def __getitem__(self, index: int) -> Track[MetadataT]:
        if not isinstance(index, int):
            raise TypeError('index must be an integer')

        return self._queue[index]

    def __setitem__(self, index: int, value: Track[MetadataT]) -> None:
        if not isinstance(index, int):
            raise TypeError('index must be an integer')

        self._queue[index] = value

    def __delitem__(self, index: int) -> None:
        if not isinstance(index, int):
            raise TypeError('index must be an integer')

        del self._queue[index]

    def __iter__(self) -> Iterator[Track[MetadataT]]:
        return iter(self._queue)

    def __contains__(self, item: Track[MetadataT]) -> bool:
        return item in self._queue

    def __reversed__(self) -> Iterator[Track[MetadataT]]:
        return reversed(self._queue)


class ConsumptionQueue(BaseQueue[MetadataT], Generic[MetadataT]):
    """A queue that gets rid of tracks as they are retrieved.

    For a more common use case of a queue where tracks are kept, see :class:`.Queue`.

    Attributes
    ----------
    max_size: Optional[:class:`int`]
        The maximum amount of tracks this queue can hold. ``None`` if no
        limit was set.

    Parameters
    ----------
    max_size: Optional[:class:`int`]
        The maximum amount of tracks this queue should hold.
        Leave blank to allow an infinite amount of tracks.
    factory: () -> :py:class:`~collections.deque`
        The factory function or class to use to create the internal queue.
        Defaults to the built-in :class:`collections.deque` itself.
    """

    __slots__ = ('max_size', '_current', '_queue')

    def __init__(
        self,
        *,
        max_size: Optional[int] = None,
        factory: Callable[[], _InternalQueue[MetadataT]] = deque,
    ) -> None:
        self.max_size: Optional[int] = max_size
        self._current: Optional[Track[MetadataT]] = None
        self._queue: _InternalQueue[MetadataT] = factory()

    @property
    def current(self) -> Optional[Track[MetadataT]]:
        return self._current

    @property
    def up_next(self) -> Optional[Track[MetadataT]]:
        return None if self.is_empty() else self._queue[0]

    @property
    def upcoming(self) -> List[Track[MetadataT]]:
        return list(self._queue)

    def _get(self) -> Optional[Track[MetadataT]]:
        try:
            self._current = self._queue.popleft()
        except IndexError:
            return None
        return self.current

    def copy(self: ConsumptionQueueT) -> ConsumptionQueueT:
        new = self.__class__(max_size=self.max_size)
        new._queue = self._queue.copy()
        return new

    def jump_to(self, index: int) -> Track[MetadataT]:
        if result := self.skip(index):
            return result

        raise IndexError(f'index {index} out of range')


class LoopType(IntEnum):
    """|enum|

    The track looping type of a :class:`.Queue`.
    """

    #: The queue will not loop anything.
    none = 0

    #: The queue will loop its current track.
    track = 1

    #: The queue will loop through itself.
    queue = 2


class Queue(BaseQueue[MetadataT], Generic[MetadataT]):
    """A queue that keeps its tracks, moving a pointer to each track which is retrieved.

    Because this is the most common use case for queues, this is just named "Queue".
    For a queue that consumes tracks as they are retrieved, see :class:`.ConsumptionQueue`.

    This also adds the ability for looping.

    Attributes
    ----------
    max_size: Optional[:clas:`int`]
        The maximum amount of tracks this queue can hold. ``None`` if no
        limit was set.
    loop_type: :class:`.LoopType`
        The looping policy this queue is using.

    Parameters
    ----------
    max_size: Optional[:class:`int`]
        The maximum amount of tracks this queue should hold.
        Leave blank to allow an infinite amount of tracks.
    loop_type: :class:`.LoopType`
        The loop type to use. Defaults to :attr:`~.LoopType.none`.
    factory: () -> :py:class:`~collections.deque`
        The factory function or class to use to create the internal queue.
        Defaults to the built-in :class:`collections.deque` itself.
    """

    __slots__ = ('max_size', 'loop_type', '_queue', '_index')

    def __init__(
        self,
        *,
        max_size: Optional[int] = None,
        loop_type: LoopType = LoopType.none,
        factory: Callable[[], _InternalQueue[MetadataT]] = deque,
    ) -> None:
        self.max_size: Optional[int] = max_size
        self.loop_type: LoopType = loop_type

        self._queue: _InternalQueue[MetadataT] = factory()
        self._index: int = -1

    @property
    def current(self) -> Optional[Track[MetadataT]]:
        try:
            return None if self._index < 0 else self._queue[self._index]
        except IndexError:
            return None

    @property
    def current_index(self) -> Optional[int]:
        """Optional[:class:`int`]: The index of the current track the queue is pointing to.
        This could be an index out of bounds if the queue has exhausted all tracks.

        This is ``None`` if the queue is not pointing to a track.
        """
        return None if self._index < 0 else self._index

    @current_index.setter
    def current_index(self, value: Optional[int]) -> None:
        if value is None:
            self._index = -1
            return

        self.jump_to(value)

    @property
    def up_next(self) -> Optional[Track[MetadataT]]:
        if self.loop_type is LoopType.track:
            return self.current
        try:
            return self._queue[self._index + 1]
        except IndexError:
            return self._queue[0] if self.loop_type is LoopType.queue and not self.is_empty() else None

    @property
    def upcoming(self) -> List[Track[MetadataT]]:
        result = []
        index = self._index + 1

        while True:
            try:
                result.append(self._queue[index])
            except IndexError:
                break

            index += 1

        return result

    def _get(self) -> Optional[Track[MetadataT]]:
        if self.loop_type is LoopType.track:
            return self._skip() if self._index == -1 else self.current

        return self._skip()

    def _insert(self, index: int, track: Track[MetadataT]) -> None:
        if index <= self._index:
            self._index += 1

    def _skip(self) -> Optional[Track[MetadataT]]:
        if self._index == -1 or self.current is not None:
            self._index += 1

        if self.current is None and self.loop_type is LoopType.queue:
            self._index = 0

        return self.current

    def jump_to(self, index: int) -> Track[MetadataT]:
        if not isinstance(index, int):
            raise TypeError("index must be an int")

        self._index = index
        if not self.current:
            raise IndexError(f'no track exists at index {index}')

        return self.current

    def remove_index(self, index: int = 0) -> Track[MetadataT]:
        if not isinstance(index, int):
            raise TypeError('index must be an int')

        if index < self._index:
            self._index -= 1

        return super().remove_index(index)

    def remove(self, item: Track[MetadataT]) -> None:
        before = self.current
        super().remove(item)

        if before is not self.current:
            self._index -= 1

    def reset(self, *, hard: bool = False) -> None:
        """Resets the queue pointer.

        Parameters
        ----------
        hard: :class:`bool`
            Whether :meth:`get` should be called to retrieve the first track again.
            If ``False`` the queue will just reset to the first track.

            Defaults to ``False``.
        """
        self._index = -hard

    def shift(self) -> None:
        """Shifts the queue so that the first track is now the current track.

        .. warning::
            This will discard tracks that come before the current track in the queue.
        """
        for _ in range(self._index - 1):
            self._queue.popleft()

        self._index = 0

    def clear(self) -> None:
        super().clear()
        self.reset(hard=True)

    def copy(self: QueueT) -> QueueT:
        new = self.__class__(max_size=self.max_size, loop_type=self.loop_type)
        new.current_index = self._index
        new._queue = self._queue.copy()
        return new


def _waiter_cls(base: Type[BaseQueueT]) -> Type[BaseQueueT]:
    # noinspection PyAbstractClass
    @wraps(base, updated=())
    class Wrapped(base):  # type: ignore
        __slots__ = ('_fut', '_loop')

        _fut: Optional[asyncio.Future]
        _loop: asyncio.AbstractEventLoop

        def _dispatch(self) -> None:
            if not self._fut or self._fut.done():
                return

            self._fut.set_result(None)

        def _add(self, track: Track) -> None:
            super()._add(track)
            self._dispatch()

        def _insert(self, index: int, track: Track) -> None:
            super()._insert(index, track)
            self._dispatch()

        def cancel_waiter(self) -> None:
            """Cancels the waiter in this queue.

            In consequence, :exception:`asyncio.CancelledError` will be raised where you have awaited this waiter.
            """
            if self._fut:
                self._fut.cancel()

        def reset(self, *args: Any, **kwargs: Any) -> Any:
            self.cancel_waiter()

            if reset := getattr(super(), 'reset', None):
                return reset(*args, **kwargs)

        async def _start_wait(self, method: Callable[P, Optional[R]], *args: P.args, **kwargs: P.kwargs) -> R:
            if self._fut is None or self._fut.done():
                self._fut = self._loop.create_future()

            try:
                await self._fut
            except asyncio.CancelledError:
                self._fut = None
                raise

            result = method(*args, **kwargs)
            assert result is not None
            return result

        async def get_wait(self) -> Track:
            # sourcery skip: assign-if-exp, reintroduce-else
            """|coro|

            Runs :meth:`get` but waits for a track to be available beforehand.
            This guarantees the track returned will not be ``None``.

            Returns
            -------
            :class:`Track`
                The track that was retrieved.
            """
            if track := self.get():
                return track

            return await self._start_wait(self.get)

        async def skip_wait(self) -> Track:
            # sourcery skip: assign-if-exp, reintroduce-else
            """|coro|

            Runs :meth:`skip` but waits for a track to be available beforehand.
            This guarantees the track returned will not be ``None``.

            Returns
            -------
            :class:`Track`
                The track that was skipped.
            """
            if track := self.skip():
                return track

            return await self._start_wait(self.skip)

        def copy(self: BaseQueueT) -> BaseQueueT:
            copy = super().copy()
            copy._fut = self._fut  # type: ignore
            copy._loop = self._loop  # type: ignore
            return copy

        async def __aiter__(self) -> AsyncIterator[Track]:
            while True:
                try:
                    yield await self.get_wait()
                except asyncio.CancelledError:
                    break

    return Wrapped


@_waiter_cls
class WaitableConsumptionQueue(ConsumptionQueue[MetadataT], Generic[MetadataT]):
    """A :class:`.ConsumptionQueue` that supports waiting for queues by storing a persistent :py:class:`asyncio.Future`.

    See :class:`.ConsumptionQueue` for more information on parameters and attributes.

    The only difference in the constructor signature is that it additionally takes a ``loop`` kwarg,
    specifying the event loop in which wait-futures will be created upon. This is optional.
    """

    __slots__ = ('_fut', '_loop')

    def __init__(
        self,
        *,
        max_size: Optional[int] = None,
        factory: Callable[[], _InternalQueue[MetadataT]] = deque,
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ) -> None:
        super().__init__(max_size=max_size, factory=factory)

        self._fut = None
        self._loop = loop or asyncio.get_event_loop()

    if TYPE_CHECKING:
        def cancel_waiter(self) -> None: ...
        async def get_wait(self) -> Track[MetadataT]: ...
        async def skip_wait(self) -> Track[MetadataT]: ...
        async def __aiter__(self) -> AsyncIterator[Track[MetadataT]]: ...


@_waiter_cls
class WaitableQueue(Queue[MetadataT], Generic[MetadataT]):
    """A :class:`.Queue` that supports waiting for queues by storing a persistent :py:class:`asyncio.Future`.

    See :class:`.Queue` for more information on parameters and attributes.

    The only difference in the constructor signature is that it additionally takes a ``loop`` kwarg,
    specifying the event loop in which wait-futures will be created upon. This is optional.
    """

    __slots__ = ('_fut', '_loop')

    def __init__(
        self,
        *,
        max_size: Optional[int] = None,
        loop_type: LoopType = LoopType.none,
        factory: Callable[[], _InternalQueue[MetadataT]] = deque,
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ) -> None:
        super().__init__(max_size=max_size, loop_type=loop_type, factory=factory)

        self._fut = None
        self._loop = loop or asyncio.get_event_loop()

    if TYPE_CHECKING:
        def cancel_waiter(self) -> None: ...
        async def get_wait(self) -> Track[MetadataT]: ...
        async def skip_wait(self) -> Track[MetadataT]: ...
        async def __aiter__(self) -> AsyncIterator[Track[MetadataT]]: ...
