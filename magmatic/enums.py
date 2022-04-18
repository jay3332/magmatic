from enum import Enum
from typing import TYPE_CHECKING

__all__ = (
    'OpCode',
    'EventType',
    'LoadType',
    'Source',
    'LoadSource',
    'ErrorSeverity',
    'TrackEndReason',
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

    This is usually used internally.
    """
    if TYPE_CHECKING:
        value: str

    #: One single track was loaded.
    track_loaded = 'TRACK_LOADED'

    #: A playlist containing multiple tracks were loaded.
    playlist_loaded = 'PLAYLIST_LOADED'

    #: Tracks that matched the search result were loaded. This usually indicates multiple tracks.
    search_result = 'SEARCH_RESULT'

    #: No tracks matched the given query.
    no_matches = 'NO_MATCHES'

    #: The track loading request failed.
    load_failed = 'LOAD_FAILED'

    # Aliases
    track = track_loaded
    playlist = playlist_loaded
    search = search_result


class Source(Enum):
    """|enum|

    The source to use when searching for a track.
    See :meth:`.Node.search_tracks` for more information on track searching.

    This is not to be confused with :class:`.LoadSource`, which represents the source of
    a track that has already been loaded.
    """
    if TYPE_CHECKING:
        value: str

    #: Searches YouTube for tracks.
    youtube = 'ytsearch'

    #: Searches YouTube Music for tracks.
    youtube_music = 'ytmsearch'

    #: Searches SoundCloud for tracks.
    soundcloud = 'scsearch'

    #: Searches Spotify for tracks.
    spotify = 'spotify'  # This one is special

    #: Searches a local file for tracks.
    local = 'local'  # This one is also special; do not include the directive in the search query


class LoadSource(Enum):
    """|enum|

    Represents the source of a loaded track, e.g. YouTube.

    This is not to be confused with :class:`.Source`, which is to be used when searching for tracks.
    Rather, this enum represents the source of a track that has been loaded.
    """
    if TYPE_CHECKING:
        value: str

    #: The track was loaded from a YouTube video or YouTube music track.
    youtube = 'youtube'

    #: The track was loaded from a SoundCloud track.
    soundcloud = 'soundcloud'

    # TODO: Upsell Spotify support when it's available.
    #: The track was loaded from Spotify.
    spotify = 'spotify'

    #: The track was loaded from a Twitch track.
    twitch = 'twitch'

    #: The track was loaded from a Bandcamp track.
    bandcamp = 'bandcamp'

    #: The track was loaded from Vimeo.
    vimeo = 'vimeo'

    #: The track was loaded from Beam.
    beam = 'beam'

    #: The track was loaded from Nico.
    nico = 'nico'

    #: The track was loaded from getyarn.io.
    getyarn = 'getyarn.io'

    #: The track was loaded from a local file.
    local = 'local'

    #: The track was loaded from a URL via HTTP.
    http = 'http'

    #: The track was loaded from a stream of audio.
    stream = 'stream'


class ErrorSeverity(Enum):
    """|enum|

    Represents the severity of an error received from Lavalink.
    """

    if TYPE_CHECKING:
        value: str

    #: This error is a common, non-fatal error. This is caused by the user input itself and not by Lavalink.
    common = 'COMMON'

    #: This error's cause may not be known and is usually caused by outside factors, e.g. a response in an unexpected format.
    suspicious = 'SUSPICIOUS'

    #: This error was caused by an issue with Lavalink.
    fault = 'FAULT'


class TrackEndReason(Enum):
    """|enum|

    Represents why a track has ended.
    """

    if TYPE_CHECKING:
        value: str

    #: The track has finished playing, or an exception was raised during playback.
    finished = 'FINISHED'

    #: The track failed to start, throwing an exception before providing audio.
    load_failed = 'LOAD_FAILED'

    #: The track was stopped by the user.
    stopped = 'STOPPED'

    #: The track was replaced by another track. See the ``replace`` parameter in :meth:`.Player.play` for more information.
    replaced = 'REPLACED'

    #: The track was stopped because the cleanup threshold for the player was reached.
    cleanup = 'CLEANUP'

    @property
    def may_start_next(self) -> bool:
        """bool: Whether it is safe to start playing another track."""
        return self is TrackEndReason.finished or self is TrackEndReason.load_failed
