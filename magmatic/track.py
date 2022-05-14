from __future__ import annotations

from typing import Any, ClassVar, Dict, Generic, Iterator, List, Optional, TYPE_CHECKING, Type, TypeVar, Sequence, cast

from discord.ext.commands import BadArgument, Context, Converter, Parameter, run_converters

from .errors import NoMatches
from .enums import LoadSource, Source

if TYPE_CHECKING:
    TrackT = TypeVar('TrackT', bound='Track')

MetadataT = TypeVar('MetadataT')
MetadataCT = TypeVar('MetadataCT', bound=Type[Any])
MetadataCT_co = TypeVar('MetadataCT_co', bound=Type[Any], covariant=True)

__all__ = (
    'Track',
    'LocalTrack',
    'YoutubeTrack',
    'YoutubeMusicTrack',
    'SoundCloudTrack',
    'SpotifyTrack',
    'Playlist',
)


class Track(Generic[MetadataT]):
    """Represents a playable track, usually retrieved by search.

    See :meth:`.Node.search_track` and :meth:`.Node.search_tracks` for more information.
    These should not be constructed manually.

    Attributes
    ----------
    id: :class:`int`
        The base 64 ID of the track.

        You can use this to rebuild this track object; see :meth:`.Node.fetch_track`
        or :meth:`.Node.fetch_tracks` for information on how.
    title: :class:`str`
        The title of the track.
    author: Optional[:class:`str`]
        The author of the track. ``None`` if the author is unknown.
    uri: Optional[:class:`str`]
        The URI (or URL) which can be used to access this track.
        This may be ``None`` if the track is a local track.
    identifier: Optional[:class:`str`]
        The identifier of this track.
        This can be ``None`` depending on the video's :attr:`source`.
    duration: :class:`float`
        The duration of the track in seconds.
    position: Optional[:class:`float`]
        The current position of the track in seconds.
        If this isn't applicable, this will be ``None``.
    playlist: Optional[:class:`Playlist`]
        The playlist object this track belongs to.

        This will be ``None`` if this track is not part of a playlist,
        or if the track was not loaded from a playlist.
    metadata
        The metadata manually provided with the track. This is always provided by you, the user.
        Could be useful for associating a requester with the track.

        If no metadata was provided, this will be ``None``.
    """

    __slots__ = (
        'id',
        'title',
        'author',
        'uri',
        'identifier',
        'metadata',
        'playlist',
        'duration',
        'position',
        '_source',
        '_stream',
        '_seekable',
    )

    def __init__(
        self,
        *,
        id: str,
        data: Dict[str, Any],
        metadata: MetadataT = None,
    ) -> None:
        self.id: str = id
        self.title: str = data['title']
        self.author: Optional[str] = data.get('author')
        self.uri: Optional[str] = data.get('uri')
        self.identifier: Optional[str] = data.get('identifier')
        self.metadata: MetadataT = metadata
        self.playlist: Optional[Playlist] = None

        self.duration: float = data['length'] / 1000
        self.position: Optional[float] = None

        # In older Lavalink versions, this field does not exist
        # In newer versions, this could be null if the position is not applicable
        if data.get('position') is not None:
            self.position = data['position'] / 1000

        # Similar situation with position
        self._source: Optional[LoadSource] = None
        if source := data.get('sourceName'):
            self._source = LoadSource(source)

        # These fields will always be available in newer Lavalink versions,
        # here I'm giving these defaults for backwards compatibility.
        self._stream: bool = data.get('isStream', False)
        self._seekable: bool = data.get('isSeekable', True)

    @property
    def source(self) -> Optional[LoadSource]:
        """Optional[:class:`.LoadSource`]: The load source of this track, e.g. YouTube.

        This may be none if the track was manually loaded or your Lavalink version does not support it.
        """
        return self._source

    @property
    def thumbnail(self) -> Optional[str]:
        """Optional[:class:`str`]: The URL to the thumbnail image for this track.

        This only exists for certain audio sources.
        """
        # Lavaplayer doesn't properly support artworkUri on the master branch.
        # Until then, this property will have to be implemented manually.
        if self.source is LoadSource.youtube:
            return f'https://i.ytimg.com/vi/{self.identifier}/hq720.jpg'

    def is_stream(self) -> bool:
        """bool: Returns ``True`` if this track is a stream."""
        return self._stream

    def is_seekable(self) -> bool:
        """bool: Returns ``True`` if this track is seekable."""
        return self._seekable

    def __repr__(self) -> str:
        return f'<Track id={self.id!r} title={self.title!r} uri={self.uri!r}>'

    def __eq__(self, other: Any) -> bool:
        return self.id == other.id if isinstance(other, self.__class__) else False


class _MetadataAwareTrackConverter(Converter[Track[MetadataCT_co]], Generic[MetadataCT_co]):
    _unknown_parameter_sentinel: ClassVar[Any] = Parameter(name='unknown', kind=Parameter.POSITIONAL_OR_KEYWORD)

    def __init__(self, cls: Type[_TrackConverter[Any]], converter: MetadataCT_co) -> None:
        self.cls: Type[_TrackConverter[Any]] = cls
        self.converter: MetadataCT_co = converter

    async def convert(self, ctx: Context[Any], argument: str) -> Track[MetadataCT_co]:  # type: ignore
        param = ctx.current_parameter or self._unknown_parameter_sentinel
        metadata = await run_converters(ctx, self.converter, argument, param)
        track = await self.cls.convert(ctx, argument)
        track.metadata = metadata

        return track  # type: ignore


class _TrackConverter(Track[MetadataCT]):
    _preferred_source: ClassVar[Source]

    def __class_getitem__(cls, item: MetadataCT) -> _MetadataAwareTrackConverter[MetadataCT]:
        if cls is _TrackConverter:
            return cast('_MetadataAwareTrackConverter[MetadataCT]', cls)

        return _MetadataAwareTrackConverter(cls, item)

    @classmethod
    async def convert(cls, _ctx: Context[Any], argument: str) -> Track[None]:
        from .pool import get_node

        node = get_node()
        try:
            track = await node.search_track(query=argument, source=cls._preferred_source, metadata=None)
            if track is None:
                raise NoMatches(node, argument, cls._preferred_source)

            return track
        except NoMatches:
            raise BadArgument(f'No tracks found with query {argument!r}')


class YoutubeTrack(_TrackConverter[MetadataCT]):
    """A subclass of :class:`.Track` solely used for conversion purposes.

    This class when used as a discord.py :class:`Converter <discord.ext.commands.Context>` will search for the first
    track with the source set to :attr:`.Source.youtube`.
    """

    _preferred_source = Source.youtube


class YoutubeMusicTrack(_TrackConverter[MetadataCT]):
    """A subclass of :class:`.Track` solely used for conversion purposes.

    This class when used as a discord.py :class:`Converter <discord.ext.commands.Context>` will search for the first
    track with the source set to :attr:`.Source.youtube_music`.
    """

    _preferred_source = Source.youtube_music


class SoundCloudTrack(_TrackConverter[MetadataCT]):
    """A subclass of :class:`.Track` solely used for conversion purposes.

    This class when used as a discord.py :class:`Converter <discord.ext.commands.Context>` will search for the first
    track with the source set to :attr:`.Source.soundcloud`.
    """

    _preferred_source = Source.soundcloud


class SpotifyTrack(_TrackConverter[MetadataCT]):
    """A subclass of :class:`.Track` solely used for conversion purposes.

    This class when used as a discord.py :class:`Converter <discord.ext.commands.Context>` will search for the first
    track with the source set to :attr:`.Source.spotify`.
    """

    _preferred_source = Source.spotify


class LocalTrack(_TrackConverter[MetadataCT]):
    """A subclass of :class:`.Track` solely used for conversion purposes.

    This class when used as a discord.py :class:`Converter <discord.ext.commands.Context>` will search for the first
    track with the source set to :attr:`.Source.local`.
    """

    _preferred_source = Source.local


class Playlist(Sequence[Track[MetadataT]], Generic[MetadataT]):
    """Represents a playlist of tracks, usually retrieved by search.

    See :meth:`.Node.search_track` and :meth:`.Node.search_tracks` for more information.
    These should not be constructed manually.

    This implements :class:`collections.abc.Sequence`.

    Attributes
    ----------
    name: :class:`str`
        The name of the playlist.
    selected_track_index: :class:`int`
        The index of the currently selected track. ``-1`` if no track is selected.
    metadata
        The metadata manually provided with the playlist. This is always provided by you, the user.
        Could be useful for associating a requester with the playlist.

        If no metadata was provided, this will be ``None``.
    """

    def __init__(self, tracks: List[Track[MetadataT]], data: Dict[str, Any], *, metadata: MetadataT) -> None:
        self._tracks: List[Track[MetadataT]] = tracks
        self._source: Optional[LoadSource] = self.first and self.first.source

        self.name: str = data['name']
        self.selected_track_index = data['selectedTrack']
        self.metadata: MetadataT = metadata

        for track in tracks:
            track.playlist = self

    @property
    def first(self) -> Optional[Track[MetadataT]]:
        """Optional[:class:`Track`]: Returns the first track in the playlist."""
        return None if self.is_empty() else self._tracks[0]

    @property
    def selected_track(self) -> Optional[Track[MetadataT]]:
        """Optional[:class:`Track`]: The currently selected track in the playlist.

        ``None`` if no track is selected.
        """
        if self.selected_track_index == -1:
            return None

        return self[self.selected_track_index]

    @property
    def source(self) -> Optional[LoadSource]:
        """:class:`LoadSource`: The load source of this playlist.

        This is retrieved from the first track in the playlist, so if this
        is an empty playlist this will be ``None``.

        See also
        --------
        :attr:`.Track.source`
        """
        return self._source

    @property
    def tracks(self) -> List[Track[MetadataT]]:
        """list[:class:`.Track`]: A list of the tracks in this playlist."""
        return self._tracks.copy()

    def is_empty(self) -> bool:
        """bool: Returns whether the playlist is empty."""
        return not self._tracks

    def seek(self, index: int) -> Track[MetadataT]:
        """Seeks to the track of the given index.

        This changes :attr:`selected_track_index` and in consequence :attr:`selected_track`.

        Parameters
        ----------
        index: int
            The index of the track to seek to.

        Returns
        -------
        :class:`Track`
            The track that was seeked to.
        """
        self.selected_track_index = index
        if self.selected_track is None:
            raise IndexError('Selected track index out of range')

        return self.selected_track

    def __getitem__(self, index: int) -> Track[MetadataT]:
        return self._tracks[index]

    def __iter__(self) -> Iterator[Track[MetadataT]]:
        return iter(self._tracks)

    def __len__(self) -> int:
        return len(self._tracks)

    def __repr__(self) -> str:
        return f'<Playlist name={self.name!r} selected_track={self.selected_track!r}>'
