from __future__ import annotations

from abc import ABC
from typing import Any, ClassVar, Dict, TYPE_CHECKING, TypeVar, cast

from .enums import ErrorSeverity, EventType, TrackEndReason

if TYPE_CHECKING:
    from .node import Node
    from .player import Player
    from .track import Track

    MetadataT = TypeVar('MetadataT')

_None = cast(Any, None)

__all__ = (
    'TrackStartEvent',
    'TrackEndEvent',
    'TrackStuckEvent',
    'TrackExceptionEvent',
    'WebSocketCloseEvent',
)


class BaseEvent(ABC):
    """The base class that all event models inherit from.

    Attributes
    ----------
    player: :class`.Player`
        The player that triggered the event.
    """

    __slots__ = ('player',)

    event_name: ClassVar[str]
    type: ClassVar[EventType]

    def __init__(self, player: Player) -> None:
        self.player: Player = player

    @property
    def node(self) -> Node:
        """:class:`.Node`: The Lavalink node that received this event."""
        return self.player.node

    def __repr__(self) -> str:
        info = ' '.join(f'{attr}={getattr(self, attr)!r}' for attr in self.__slots__)
        return f'<{self.__class__.__name__} {info}>'


class TrackAwareEvent(BaseEvent):
    """The base class for track-related events.

    Attributes
    ----------
    player: :class:`.Player`
        The player this event is associated with.
    track_id: str
        The base 64 ID of the relevant.
        To resolve this into a full track object, see :meth:`track`.
    """

    __slots__ = ('player', 'track_id')

    def __init__(self, player: Player, track_id: str) -> None:
        super().__init__(player)

        self.track_id: str = track_id

    async def track(self, *, metadata: MetadataT = _None) -> Track[MetadataT]:
        """|coro|

        Resolves the track ID into a :class:`.Track` object.

        This will make a request to Lavalink to decode the track ID associated with this event.
        See :meth:`Node.fetch_track` for more information.

        Parameters
        ----------
        metadata
            The metadata to associate with the fetched track.

            Could be useful for associating a requester with the track.
            This is optional and defaults to ``None``.

        Returns
        -------
        :class:`.Track`
            The track object associated with this event.

        Raises
        ------
        NotFound
            The track was not found.
        """
        return await self.player.node.fetch_track(self.track_id, metadata=metadata)


class TrackStartEvent(TrackAwareEvent):
    # noinspection PyUnresolvedReferences
    """Triggered when a track starts playing.

    Attributes
    ----------
    player: :class:`.Player`
        The player on which the track started playing on.
    track_id: str
        The base 64 ID of the track that started playing.
        To resolve this into a full track object, see :meth:`track`.
    """

    __slots__ = ('player', 'track_id')

    event_name = 'track_start'
    type = EventType.track_start


class TrackEndEvent(TrackAwareEvent):
    """Triggered when a track ends and stops playing.

    Attributes
    ----------
    player: :class:`.Player`
        The player on which the track ended playing on.
    track_id: str
        The base 64 ID of the track that ended playing.
        To resolve this into a full track object, see :meth:`track`.
    reason: :class:`.TrackEndReason`
        The reason the track ended.
    """

    __slots__ = ('player', 'track_id', 'reason')

    event_name = 'track_end'
    type = EventType.track_end

    def __init__(self, player: Player, track_id: str, reason: str) -> None:
        super().__init__(player, track_id)

        self.reason: TrackEndReason = TrackEndReason(reason)

    @property
    def may_start_next(self) -> bool:
        """bool: Whether it is safe for the player to start playing the next track."""
        return self.reason.may_start_next


class TrackExceptionEvent(TrackAwareEvent):
    """Triggered when a track throws an exception during playback.

    Attributes
    ----------
    player: :class:`.Player`
        The player on which the track threw an exception on.
    track_id: str
        The base 64 ID of the track that threw an exception.
        To resolve this into a full track object, see :meth:`track`.
    message: str
        The exception message provided by Lavalink.
    severity: :class:`.ErrorSeverity`
        The severity of the exception.
    cause: str
        The cause of the exception.
    """

    __slots__ = ('player', 'track_id', 'message', 'severity', 'cause')

    event_name = 'track_exception'
    type = EventType.track_exception

    def __init__(self, player: Player, track_id: str, exception: Dict[str, Any]) -> None:
        super().__init__(player, track_id)

        self.message: str = exception['message']
        self.severity: ErrorSeverity = ErrorSeverity(exception['severity'])
        self.cause: str = exception['cause']


class TrackStuckEvent(TrackAwareEvent):
    """Triggered when a track is stuck.

    Attributes
    ----------
    player: :class:`.Player`
        The player on which the track is stuck on.
    track_id: str
        The base 64 ID of the track that is stuck.
        To resolve this into a full track object, see :meth:`track`.
    threshold: float
        The threshold in seconds at which the track is considered stuck.
    """

    __slots__ = ('player', 'track_id', 'threshold')

    event_name = 'track_stuck'
    type = EventType.track_stuck

    def __init__(self, player: Player, track_id: str, threshold_ms: int) -> None:
        super().__init__(player, track_id)

        self.threshold: float = threshold_ms / 1000


class WebSocketCloseEvent(BaseEvent):
    """Triggered when the websocket connection is closed.

    Attributes
    ----------
    code: int
        The websocket close code.
    reason: str
        The websocket close reason.
    by_remote: bool
        Whether the websocket was closed remotely.
    """

    __slots__ = ('code', 'reason', 'by_remote')

    event_name = 'websocket_close'
    type = EventType.websocket_closed

    def __init__(self, player: Player, code: int, reason: str, by_remote: bool = True) -> None:
        super().__init__(player)

        self.code: int = code
        self.reason: str = reason
        self.by_remote: bool = by_remote
