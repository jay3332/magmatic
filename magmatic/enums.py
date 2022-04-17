from enum import Enum
from typing import TYPE_CHECKING

__all__ = (
    'OpCode',
    'EventType',
)


class OpCode(Enum):
    """|enum|

    Represents an inbound Op-code received from Lavalink's websocket.

    This is only used internally and should rarely be used.
    """
    if TYPE_CHECKING:
        value: str

    #: This payload provides node statistics.
    stats = 'stats'

    #: This payload signals a Lavalink event.
    event = 'event'

    #: This payload requests updates to a player.
    player_update = 'playerUpdate'

    # Aliases
    update = player_update


class EventType(Enum):
    """|enum|

    Represents the type of event received from Lavalink's websocket via the ``event`` op-code.

    This is only used internally and should rarely be used.
    """
    if TYPE_CHECKING:
        value: str

    #: This event signals that a track has started playing.
    track_start = 'TrackStartEvent'

    #: This event signals that a track has stopped playing.
    track_end = 'TrackEndEvent'

    #: This event signals that a track has been stuck for some reason.
    track_stuck = 'TrackStuckEvent'

    #: The event signals an error during track playback.
    track_exception = 'TrackExceptionEvent'

    #: This event signals that the Lavalink websocket was disconnected during playback.
    websocket_closed = 'WebSocketClosedEvent'


class LoadType(Enum):
    """|enum|

    Represents the response type of a track loading request.
    """
    if TYPE_CHECKING:
        value: str

    #: One single track was loaded.
    track_loaded = 'TRACK_LOADED'

    #: A playlist containing multiple tracks were loaded.
    playlist_loaded = 'PLAYLIST_LOADED'

    #: Tracks that matched the search result were loaded. This usually indicates multiple tracks.
    search_result = 'SEARCH_RESULT'

    #: No tracks were loaded given the query.
    no_tracks = 'NO_TRACKS'

    #: The track loading request failed.
    load_failed = 'LOAD_FAILED'

    # Aliases
    track = track_loaded
    playlist = playlist_loaded
    search = search_result


class Source(Enum):
    """|enum|

    Represents the source of a track, e.g. Youtube.
    """
    if TYPE_CHECKING:
        value: str

    #: The track was loaded from a YouTube video.
    youtube = 'youtube'

    #: The track was loaded from a YouTube Music track.
    youtube_music = 'youtube_music'

    #: The track was loaded from a SoundCloud track.
    soundcloud = 'soundcloud'

    # TODO: Upsell Spotify support when it's available.
    #: The track was loaded from Spotify.
    spotify = 'spotify'
