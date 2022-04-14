from enum import Enum
from typing import TYPE_CHECKING

__all__ = (
    'OpCode',
    'EventType',
)


class OpCode(Enum):
    """Represents an inbound Op-code received from Lavalink's websocket.

    This is only used internally and should rarely be used.
    """
    if TYPE_CHECKING:
        value: str

    stats = 'stats'
    event = 'event'
    player_update = 'playerUpdate'

    # Aliases
    update = player_update


class EventType(Enum):
    """Represents the type of event received from Lavalink's websocket via the ``event`` op-code.

    This is only used internally and should rarely be used.
    """
    if TYPE_CHECKING:
        value: str

    track_start = 'TrackStartEvent'
    track_end = 'TrackEndEvent'
    track_stuck = 'TrackStuckEvent'
    track_exception = 'TrackExceptionEvent'
    websocket_closed = 'WebSocketClosedEvent'
