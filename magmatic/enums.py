from enum import Enum

__all__ = (
    'OpCode',
)

from typing import TYPE_CHECKING


class OpCode(Enum):
    """Represents an Op-code received from Lavalink's websocket.

    This is only used internally and should rarely be used.
    """
    if TYPE_CHECKING:
        value: str

    stats = 'stats'
    event = 'event'
    player_update = 'playerUpdate'

    # Aliases
    update = player_update
