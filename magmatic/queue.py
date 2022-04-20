from __future__ import annotations

from abc import ABC
from collections import deque
from typing import Callable, Generic, Iterable, Iterator, List, Optional, Protocol, TYPE_CHECKING, TypeVar, Union

from .errors import QueueFull

MetadataT = TypeVar('MetadataT')

if TYPE_CHECKING:
    from typing_extensions import Self

    from .track import Playlist, Track

    Enqueueable = Union[Track[MetadataT], Playlist[MetadataT]]

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
        def copy(self) -> Self: ...

__all__ = (
    'BaseQueue',
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

    def is_empty(self) -> bool:
        """bool: Whether the queue is empty."""
        return not self

    def is_full(self) -> bool:
        """bool: Whether the queue is full. This is always ``False`` for queues that do not have a maximum size."""
        return self.max_size is not None and self.count >= self.max_size

    def _get(self) -> Track[MetadataT]:
        raise NotImplementedError

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

                raise QueueFull(self, track)

            self._add(track)

        return discarded

    def add_multiple(self, items: Iterable[Enqueueable[MetadataT]], *, discard: bool = False) -> List[Track[MetadataT]]:  # type: ignore
        """Adds multiple tracks or playlists to the queue.

        This is in reality just a shortcut to calling :meth:`add` for each track or playlist in the iterable.
        """
        # We choose to do it this way because sum is slow for this type of operation.
        discarded = []

        for item in items:
            discarded += self.add(item, discard=discard)

        return discarded

    def copy(self) -> Self:
        """Creates and returns a copy of the queue."""
        raise NotImplementedError

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__} count={self.count}>'

    def __bool__(self) -> bool:
        return bool(self.count)

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


class ConsumptionQueue(BaseQueue[MetadataT]):
    """A queue that gets rid of tracks as they are retrieved.

    Attributes
    ----------
    max_size: Optional[:clas:`int`]
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

    def __init__(
        self,
        *,
        max_size: Optional[int] = None,
        factory: Callable[[], _InternalQueue[MetadataT]] = deque,
    ) -> None:
        self.max_size: Optional[int] = max_size
        self._queue: _InternalQueue[MetadataT] = factory()

    def _get(self) -> Track[MetadataT]:
        return self._queue.popleft()

    def copy(self) -> Self:
        new = self.__class__(max_size=self.max_size)
        # noinspection PyNoneFunctionAssignment
        new._queue = self._queue.copy()
        return new
