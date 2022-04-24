from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from typing import (
    Any,
    Callable,
    ClassVar,
    Dict,
    Generic,
    Iterable,
    List,
    Literal,
    Optional,
    Protocol,
    TYPE_CHECKING,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
    overload,
)

import discord
from aiohttp import ClientSession, ClientWebSocketResponse, WSMsgType, WSServerHandshakeError
from discord.backoff import ExponentialBackoff

from .enums import ErrorSeverity, EventType, LoadType, OpCode, Source
from .errors import (
    AuthorizationFailure,
    ConnectionFailure,
    HTTPException,
    HandshakeFailure,
    LoadFailed,
    NoMatches,
    NotFound,
    PlayerNotFound,
)
from .events import (
    TrackStartEvent,
    TrackEndEvent,
    TrackExceptionEvent,
    TrackStuckEvent,
    WebSocketCloseEvent,
)
from .player import Player
from .track import Playlist, Track
from .stats import Stats

if TYPE_CHECKING:
    from discord.abc import Snowflake
    from discord.guild import VocalGuildChannel

    RequestMethod = Literal['GET', 'POST', 'PUT', 'PATCH', 'DELETE']
    PlayerT = TypeVar('PlayerT', bound=Player[Any])
    MetadataT = TypeVar('MetadataT')  # This could be covariant, but usually the type will be resolved indirectly

ClientT = TypeVar('ClientT', bound=discord.Client)
JsonT = TypeVar('JsonT', bound=Union[Dict[str, Any], List[Any], Any])
_None = cast(Any, None)

__all__ = (
    'Node',
)

log: logging.Logger = logging.getLogger(__name__)


class JSONSerializer(Protocol[JsonT]):
    def loads(self, data: str, /) -> JsonT:
        ...

    def dumps(self, data: JsonT, /) -> str:
        ...


class ConnectionManager:
    """Manages the connection of a :class:`Node`.

    This is used internally.
    """

    __slots__ = (
        'node',
        'host',
        'port',
        'loop',
        'session',
        'heartbeat_interval',
        '_password',
        '_ws_protocol',
        '_http_protocol',
        '_ws',
        '_ws_resume_key',
        '_listener',
        '_serializer',
        '_keep_alive',
    )

    REQUEST_MAX_TRIES: ClassVar[int] = 1

    def __init__(
        self,
        host: str,
        port: int,
        password: Optional[str] = None,
        *,
        secure: bool = False,
        loop: asyncio.AbstractEventLoop,
        session: Optional[ClientSession] = None,
        heartbeat_interval: float = 30.0,
        prefer_http: bool = False,
        serializer: JSONSerializer[Dict[str, Any]] = json,
        resume: bool = False,
        node: Node,
    ) -> None:
        self.node: Node[Any] = node
        self.host: str = host
        self.port: int = port
        self.loop: asyncio.AbstractEventLoop = loop
        self.session: ClientSession = session or ClientSession()
        self.heartbeat_interval: float = heartbeat_interval

        self._password: Optional[str] = password
        self._ws_protocol: str = 'http' if prefer_http else 'ws'
        self._http_protocol: str = 'https' if secure else 'http'

        if secure:
            self._ws_protocol += 's'

        self._ws: Optional[ClientWebSocketResponse] = None
        self._ws_resume_key: Optional[str] = os.urandom(8).hex() if resume else None
        self._listener: Optional[asyncio.Task] = None
        self._serializer: JSONSerializer[Dict[str, Any]] = serializer
        self._keep_alive: bool = True

    @property
    def origin(self) -> str:
        """:class:`str`: The base URI origin to use when connecting or requesting to Lavalink."""
        return f'{self.host}:{self.port}'

    @property
    def url(self) -> str:
        """:class:`str`: The URL to use when connecting to the websocket."""
        return f'{self._ws_protocol}://{self.origin}'

    @property
    def http_url(self) -> str:
        """:class:`str`: The URL to use when requesting an endpoint from the HTTP REST API."""
        return f'{self._http_protocol}://{self.origin}'

    @property
    def headers(self) -> Dict[str, str]:
        """dict[:class:`str`, :class:`str`]: The headers to use when making a request to Lavalink."""
        from . import __version__

        if self.node.bot.user is None:
            raise RuntimeError(
                'Cannot send requests without a bot user ID. Make sure you are only connecting after you log in.',
            )

        result = {
            'User-Id': str(self.node.bot.user.id),
            'Client-Name': f'magmatic/{__version__}',
        }

        if self._password:
            result['Authorization'] = self._password

        if self._ws_resume_key:
            result['Resume-Key'] = self._ws_resume_key

        return result

    def is_connected(self) -> bool:
        """Returns whether the websocket is connected to Lavalink."""
        return self._ws is not None and not self._ws.closed

    async def connect(self, *, reconnect: bool = True) -> None:
        """Connects to Lavalink's websocket.

        Parameters
        ----------
        reconnect: bool
            Whether to reconnect if the websocket is closed. Defaults to ``True``.

        Raises
        ------
        AuthorizationFailure
            Failed to authorize with Lavalink. Your password is likely incorrect.
        HandshakeFailure
            Failed the initial handshake with Lavalink's websocket.
        ConnectionFailure
            Failed to connect to Lavalink.
        """
        if self.is_connected():
            if not reconnect:
                return

            assert self._ws is not None
            await self._ws.close()

        try:
            self._ws = await self.session.ws_connect(
                self.url,
                headers=self.headers,
                heartbeat=self.heartbeat_interval,
            )

        except WSServerHandshakeError as exc:
            if exc.status == 401:
                log.error(f'[Node {self.node.identifier!r}]: Invalid authorization passed')
                raise AuthorizationFailure(self.node)

            log.error(f'[Node {self.node.identifier!r}]: Failed to establish handshake with Lavalink: {exc}')
            raise HandshakeFailure(self.node, exc)

        except Exception as exc:
            log.error(f'[Node {self.node.identifier!r}]: Failed connection: {exc}')
            raise ConnectionFailure(self.node, exc)

        log.info(f'[Node {self.node.identifier!r}]: Connected to Lavalink')
        if self._listener and not self._listener.done():
            self._listener.cancel()

        self._listener = self.loop.create_task(self.listen())

        if not self.is_connected():
            log.error(f'[Node {self.node.identifier!r}]: Immediately disconnected from Lavalink')
            return

        if self._ws_resume_key is not None:
            await self.send_resume()

        self.node.bot.dispatch('magmatic_node_ready', self.node)

    async def disconnect(self, *, reconnect: bool = True) -> None:
        """Disconnects the current connection from Lavalink."""
        self._keep_alive = reconnect

        if self._listener and not self._listener.done():
            self._listener.cancel()

        if self._ws is not None:
            await self._ws.close()

    async def handle_message(self, data: Dict[str, Any]) -> None:
        try:
            op = OpCode(data['op'])
        except KeyError:
            log.warning(f'[Node {self.node.identifier!r}]: Invalid message received: {data!r}')
            return
        except ValueError:
            log.warning(f'[Node {self.node.identifier!r}]: Invalid op code received: {data!r}')
            return

        if op is OpCode.stats:
            self.node._stats = Stats(data)

            log.debug(f'[Node {self.node.identifier!r}]: Updated stats: {data!r}')
            return

        if 'guildId' not in data:
            log.warning(f'[Node {self.node.identifier!r}]: Invalid message received: {data!r}')
            return

        guild_id = int(data['guildId'])
        try:
            player = self.node.get_player(discord.Object(id=guild_id), fail_if_not_exists=True)
        except PlayerNotFound:
            return

        if op is OpCode.player_update:
            state = data['state']
            log.debug(f'[Node {self.node.identifier!r}]: Updating player state: {state!r}')

            player._update_state(state)

        elif op is OpCode.event:
            event_type = EventType(data['type'])

            if event_type is EventType.track_start:
                event = TrackStartEvent(player, track_id=data['track'])

            elif event_type is EventType.track_end:
                event = TrackEndEvent(player, track_id=data['track'], reason=data['reason'])
                player._track = None

            elif event_type is EventType.track_stuck:
                event = TrackStuckEvent(player, track_id=data['track'], threshold_ms=data['thresholdMs'])

            elif event_type is EventType.track_exception:
                event = TrackExceptionEvent(player, track_id=data['track'], exception=data['exception'])

            elif event_type is EventType.websocket_closed:
                log.info(f'[Node {self.node.identifier!r}]: Discord websocket closed for player {player.guild.id}')

                await player.reconnect()
                event = WebSocketCloseEvent(
                    player, code=data['code'], reason=data['reason'], by_remote=data.get('byRemote', False),
                )
            else:
                return

            self._dispatch_player_event(event.event_name, player=player, event=event)

    def _dispatch_player_event(self, name: str, *, player: Player, event: Any) -> None:
        self.node.bot.dispatch(f'magmatic_{name}', player, event)

        if method := getattr(player, 'on_' + name, False):
            self.loop.create_task(self.node.bot._run_event(method, name, event))

    async def listen(self) -> None:
        if self._ws is None:
            return

        backoff = ExponentialBackoff(base=3)

        async for message in self._ws:
            if message.type is WSMsgType.CLOSED:
                log.debug(f'[Node {self.node.identifier!r}]: Connection closed')

                delay = backoff.delay()
                log.warning(f'[Node {self.node.identifier!r}]: Attempting reconnect in {delay} seconds')

                await asyncio.sleep(delay)
                await self.connect(reconnect=self._keep_alive)

                continue

            log.debug(f'[Node {self.node.identifier!r}]: Received payload: {message}')
            if message.data == 1011:
                log.error(
                    f'[Node {self.node.identifier!r}]: Internal error occurred in Lavalink; terminating connection.',
                )

                if self._listener is not None:
                    self._listener.cancel()

                await self.disconnect()
                return

            self.loop.create_task(self.handle_message(message.json(loads=self._serializer.loads)))
    
    async def send(self, data: Dict[str, Any]) -> None:
        """Sends a message to Lavalink via websocket.

        Parameters
        ----------
        data: dict[:class:`str`, Any]
            The JSON payload represented as a :py:class:`dict`.
        """
        if self._ws is None:
            raise RuntimeError('no running websocket to send message to. did you start the node?')

        raw = self._serializer.dumps(data)
        if isinstance(raw, bytes):
            raw = raw.decode('utf-8')

        await self._ws.send_str(raw)

    async def send_voice_server_update(self, *, guild_id: int, session_id: int, event: Dict[str, Any]) -> None:
        await self.send({
            'op': 'voiceUpdate',
            'guildId': str(guild_id),
            'sessionId': session_id,
            'event': event,
        })

    async def send_play_track(
        self,
        *,
        guild_id: int,
        track: str,
        start_time: int = 0,
        end_time: Optional[int] = None,
        volume: Optional[int] = None,
        no_replace: bool = False,
        pause: bool = False,
    ) -> None:
        data = {
            'op': 'play',
            'guildId': str(guild_id),
            'track': track,
            'startTime': start_time,
            'noReplace': no_replace,
            'pause': pause,
        }

        if end_time is not None:
            data['endTime'] = end_time

        if volume is not None:
            data['volume'] = volume

        await self.send(data)

    async def send_stop(self, *, guild_id: int) -> None:
        await self.send({
            'op': 'stop',
            'guildId': str(guild_id),
        })

    async def send_pause(self, *, guild_id: int, pause: bool = True) -> None:
        await self.send({
            'op': 'pause',
            'guildId': str(guild_id),
            'pause': pause,
        })

    async def send_seek(self, *, guild_id: int, position: int) -> None:
        await self.send({
            'op': 'seek',
            'guildId': str(guild_id),
            'position': position,
        })

    async def send_volume(self, *, guild_id: int, volume: int) -> None:
        await self.send({
            'op': 'volume',
            'guildId': str(guild_id),
            'volume': volume,
        })

    async def send_destroy(self, *, guild_id: int) -> None:
        await self.send({
            'op': 'destroy',
            'guildId': str(guild_id),
        })

    async def send_filters(self, *, guild_id: int, filters: Dict[str, Any]) -> None:
        await self.send({
            'op': 'filters',
            'guildId': str(guild_id),
            **filters,
        })

    async def send_resume(self) -> None:
        if self._ws_resume_key is None:
            raise RuntimeError('no resume key to resume with')

        await self.send({
            'op': 'configureResuming',
            'key': self._ws_resume_key,
            'timeout': 60,
        })

    async def request(
        self,
        method: RequestMethod,
        endpoint: str,
        *,
        data: Optional[Dict[str, Any]] = None,
        **params: Any,
    ) -> Any:
        """|coro|

        Sends a request to an endpoint on Lavalink's REST API.

        Parameters
        ----------
        method: str
            The HTTP request method to use, e.g. ``'GET'``.
        endpoint: str
            The endpoint to send the request to.
        data: dict[:class:`str`, Any]
            The JSON data to send with the request.
        **params: Any
            The URL query parameters to send with the request.

        Returns
        -------
        dict[:class:`str`, Any]
            The JSON response from the request, serialized into a :py:class:`dict` object.

        Raises
        ------
        HTTPException
            An HTTP error occurred while sending the request.
        """
        backoff = ExponentialBackoff()
        headers = {'Authorization': self._password}

        kwargs = {
            'method': method,
            'url': f'{self.http_url}/{endpoint}',
            'headers': headers,
            'params': params,
        }
        if data is not None:
            headers['Content-Type'] = 'application/json'
            kwargs['data'] = self._serializer.dumps(data)

        for i in range(self.REQUEST_MAX_TRIES):
            async with self.session.request(**kwargs) as response:
                if not response.ok:
                    if i + 1 < self.REQUEST_MAX_TRIES:
                        delay = backoff.delay()
                        await asyncio.sleep(delay)
                        continue

                    if response.status == 404:
                        raise NotFound(response)

                    raise HTTPException(response)

                return await response.json(loads=self._serializer.loads)

        raise RuntimeError(f'{self.__class__.__name__}.REQUEST_MAX_TRIES must be at least 1')


class Node(Generic[ClientT]):
    """Represents a client which interfaces around a Lavalink node.

    These are not to be constructed manually, rather they should be created via
    :func:`.create_node` or :func:`.start_node`.

    Attributes
    ----------
    bot: :class:`discord.Client`
        The discord.py client/bot instance associated with this node.
    identifier: :class:`str`
        The identifier of this node.
    region: Optional[:class:`str`]
        The voice region of this node.
    """

    URL_REGEX: ClassVar[re.Pattern[str]] = re.compile(r'^https?://(?:www\.)?.+')

    if TYPE_CHECKING:
        _cleanup: Callable[[], None]

    def __init__(
        self,
        *,
        bot: ClientT,
        host: str = '127.0.0.1',
        port: Union[int, str] = 2333,
        password: Optional[str] = None,
        region: Optional[str] = None,
        identifier: Optional[str] = None,
        session: Optional[ClientSession] = None,
        loop: Optional[asyncio.AbstractEventLoop] = None,
        prefer_http: bool = False,
        secure: bool = False,
        resume: bool = False,
        serializer: JSONSerializer[Dict[str, Any]] = json,
    ) -> None:
        if not bot.intents.voice_states:
            raise RuntimeError('bot does not have the voice_states intent.')

        self.bot: ClientT = bot
        self.identifier: str = identifier or os.urandom(8).hex()
        self.region: Optional[str] = region

        self._loop: Optional[asyncio.AbstractEventLoop] = loop
        self._connection: ConnectionManager = ConnectionManager(
            host=host,
            port=int(port),
            password=password,
            loop=self.loop,
            session=session,
            prefer_http=prefer_http,
            secure=secure,
            resume=resume,
            serializer=serializer,
            node=self,
        )

        self._players: Dict[int, Player[ClientT]] = {}
        self._stats: Optional[Stats] = None

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        """:class:`asyncio.AbstractEventLoop`: The event loop associated with this node."""
        return self.bot.loop if self._loop is None else self._loop

    @property
    def connection(self) -> ConnectionManager:
        """:class:`ConnectionManager`: The :class:`ConnectionManager` managing this node's connection with Lavalink."""
        return self._connection

    @property
    def players(self) -> List[Player[ClientT]]:
        """list[:class:`Player`]: A list of the players handled by this node."""
        return list(self._players.values())

    @property
    def player_count(self) -> int:
        """:py:class:`int`: The number of players handled by this node."""
        return len(self._players)

    @property
    def stats(self) -> Optional[Stats]:
        """Optional[:class:`.Stats`]: Statistical information about this node, received from Lavalink."""
        return self._stats

    @property
    def host(self) -> str:
        """:class:`str`: The host origin of this node."""
        return self.connection.host

    @property
    def port(self) -> int:
        """:class:`int`: The port this node is running on."""
        return self.connection.port

    @property
    def password(self) -> Optional[str]:
        """Optional[:class:`str`]: The password used by this node to authenticate with Lavalink.

        If no password was set, this will return ``None``.
        """
        return self.connection._password

    def get_player(self, guild: Snowflake, *, cls: Type[PlayerT] = Player, fail_if_not_exists: bool = False) -> PlayerT:
        """Returns the :class:`.Player` associated with the given guild.

        If ``fail_if_not_exists`` is ``False`` and the player does not exist, one is created.

        Parameters
        ----------
        guild: :class:`discord.abc.Snowflake`
            The guild to get the player for.

            Could be a :class:`snowflake <discord.abc.Snowflake>`-like object,
            such as :class:`discord.Object`, if you cannot resolve the full guild object yet.
        cls: Type[:class:`Player`]
            The player subclass to use if you would like custom behavior. This must be a class
            that subclasses :class:`.Player`.

            Defaults to :class:`.Player`.

            .. note::
                The class passed will only be applied if a new player is created.
        fail_if_not_exists: :class:`bool`
            Whether to raise an exception if the player does not exist.

            Defaults to ``False``.

        Returns
        -------
        :class:`.Player`
            The player associated with the given guild.

        Raises
        ------
        PlayerNotFound
            ``fail_if_not_exists`` is ``True`` and the player does not exist.
        """
        if guild.id not in self._players:
            if fail_if_not_exists:
                raise PlayerNotFound(self, guild)

            self._players[guild.id] = cls(node=self, guild=guild)

        # Minor, but this saves an overhead of a function call.
        if TYPE_CHECKING:
            return cast(PlayerT, None)

        return self._players[guild.id]

    async def connect_player(
        self,
        channel: VocalGuildChannel,
        *,
        self_mute: bool = False,
        self_deaf: bool = False,
        cls: Type[PlayerT] = Player,
    ) -> PlayerT:
        """|coro|

        Creates a player for the given voice channel on this node and establishes a
        voice connection with it.

        .. note::
            To disconnect the player, call :meth:`.Player.disconnect` on the **player** object,
            which will be returned by this function.

            :meth:`.Node.disconnect` is different - it will disconnect the node.

        Parameters
        ----------
        channel: Union[:class:`discord.VoiceChannel`, :class:`discord.StageChannel`]
            The voice channel to connect to.
        self_mute: :class:`bool`
            Whether to self-mute upon connecting. Defaults to ``False``.
        self_deaf: :class:`bool`
            Whether to self-deafen upon connecting. Defaults to ``False``.
        cls: Type[:class:`Player`]
            The player subclass to use if you would like custom behavior. This must be a class
            that subclasses :class:`.Player`.

            Defaults to :class:`.Player`.

            .. note::
                The class passed will only be applied if a new player is created.

        Returns
        -------
        :class:`.Player`
            The player associated with the given voice channel.
        """
        player = self.get_player(channel.guild, cls=cls)
        await player.connect(channel, self_mute=self_mute, self_deaf=self_deaf)

        return player

    async def connect(self) -> None:
        """|coro|

        Connects this node with Lavalink by establishing a WebSocket connection.

        Raises
        ------
        AuthorizationFailure
            Failed to authorize with Lavalink. Your password is likely incorrect.
        HandshakeFailure
            Failed the initial handshake with Lavalink's websocket.
        ConnectionFailure
            Failed to connect to Lavalink.

        See also
        --------
        :meth:`.Node.start`
        """
        await self.connection.connect()

    async def start(self) -> None:
        """|coro|

        Starts this node and connects it to Lavalink.

        Raises
        ------
        AuthorizationFailure
            Failed to authorize with Lavalink. Your password is likely incorrect.
        HandshakeFailure
            Failed the initial handshake with Lavalink's websocket.
        ConnectionFailure
            Failed to connect to Lavalink.
        """
        await self.connect()

    async def disconnect(self, *, disconnect_players: bool = True) -> None:
        """|coro|

        Disconnects this node from Lavalink and clears any data associated with it.

        Parameters
        ----------
        disconnect_players: :class:`bool`
            Whether to disconnect all players on this node from their voice channels.
            Defaults to ``True``.
        """
        log.info(f'[Node {self.identifier!r}]: Disconnecting...')

        for player in list(self._players.values()):
            await player.destroy(disconnect=disconnect_players)

        await self.connection.disconnect(reconnect=False)

    async def stop(self, *, disconnect_players: bool = True) -> None:
        """|coro|

        An alias to :meth:`.Node.disconnect`, see documentation for that instead.
        """
        await self.disconnect(disconnect_players=disconnect_players)

    async def destroy(self) -> None:
        """|coro|

        Disconnects and removes this node from its associated :class:`.NodePool`.
        """
        log.info(f'[Node {self.identifier!r}]: Destroying node...')

        await self.disconnect()
        self._cleanup()

    async def request(
        self,
        method: RequestMethod,
        endpoint: str,
        *,
        data: Optional[Dict[str, Any]] = None,
        **params: Any,
    ) -> Any:
        """|coro|

        Sends a request to an endpoint on Lavalink's REST API.

        Parameters
        ----------
        method: str
            The HTTP request method to use, e.g. ``'GET'``.
        endpoint: str
            The endpoint to send the request to.
        data: :class:`dict`[:class:`str`, Any]
            JSON data to send with the request.
        **params: Any
            The URL query parameters to send with the request.

        Returns
        -------
        dict[:class:`str`, Any]
            The JSON response from the request, serialized into a :py:class:`dict` object.

        Raises
        ------
        HTTPException
            An HTTP error occurred while sending the request.
        """
        return await self.connection.request(method, endpoint, data=data, **params)

    async def _load_tracks(
        self,
        query: str,
        source: Optional[Source],
        strict: bool,
    ) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
        if source is Source.spotify:
            raise NotImplementedError('Spotify search is not implemented yet.')

        elif source is Source.local:
            source = None

        if source is not None and not strict:
            subject = query.strip('<>')
            if self.URL_REGEX.match(subject):
                source = None

        if source is not None:
            query = f'{source.value}:{query}'

        results = await self.request('GET', 'loadtracks', identifier=query)
        load_type = LoadType(results['loadType'])

        if load_type is LoadType.no_matches:
            raise NoMatches(self, query, source)

        elif load_type is LoadType.load_failed:
            exception = results['exception']
            severity = ErrorSeverity(exception['severity'])

            raise LoadFailed(self, exception['message'], severity)

        elif load_type is LoadType.playlist_loaded:
            return results['playlistInfo'], results['tracks']

        return None, results['tracks']

    @overload
    async def search_tracks(
        self,
        query: str,
        *,
        source: Optional[Source] = ...,
        strict: bool = ...,
        flatten_playlists: Literal[True] = ...,
        limit: Optional[int] = ...,
        metadata: MetadataT = ...,
    ) -> List[Track[MetadataT]]:
        ...

    @overload
    async def search_tracks(
        self,
        query: str,
        *,
        source: Optional[Source] = ...,
        strict: bool = ...,
        flatten_playlists: Literal[False] = ...,
        limit: Optional[int] = ...,
        metadata: MetadataT = ...,
    ) -> Union[List[Track[MetadataT]], Playlist[MetadataT]]:
        ...

    async def search_tracks(
        self,
        query: str,
        *,
        source: Optional[Source] = None,
        strict: bool = False,
        flatten_playlists: bool = False,
        limit: Optional[int] = None,
        metadata: MetadataT = _None,
    ) -> Union[List[Track[MetadataT]], Playlist[MetadataT]]:
        """|coro|

        Finds tracks that match the given query on the given source.

        Parameters
        ----------
        query: str
            The search query.
        source: Optional[:class:`.Source`]
            The source to search on.
            If no source is given then only URLs or specific identifiers can be passed as the query.
        strict: bool
            If ``False`` (the default), this will automatically ignore the source if a URL is passed.
            This is usually what you want.

            If ``True``, then the URL will be searched on the given source.
            This should only be used if you require the :attr:`.Track.source` to be consistent every time.
        flatten_playlists: bool
            Whether to just return a list of tracks if a playlist was found for your search query.
            When set to ``True``, this method will always return a :py:class:`list`, and never :class:`.Playlist`.

            Defaults to ``False``.
        limit: Optional[int]
            The maximum number of tracks to return. This is useful to limit the amount of
            Track objects that are created.

            For playlists, this will be ignored. Consider setting ``flatten_playlists`` to ``True``
            if this circumstance matters.

            If ``None`` (the default), then all tracks will be returned.
        metadata
            The metadata to associate with the tracks and/or playlist.
            Metadata associated with playlists will be passed down to their child tracks.

            Could be useful for associating a requester with the tracks or playlist.
            This is optional and defaults to ``None``.

        Returns
        -------
        Union[list[:class:`Track`], Playlist]
            A list of tracks that matched your search query.

            If a playlist was returned and `flatten_playlists` was set to ``True``,
            a :class:`.Playlist` object will be returned instead.

        Raises
        ------
        NoMatches
            No tracks were found with your query.
        LoadFailed
            The search query failed to load.
        """
        playlist, tracks = await self._load_tracks(query, source, strict)
        if flatten_playlists:
            playlist = None

        if limit is not None and not playlist:
            tracks = tracks[:limit]

        tracks = [
            Track(id=track['track'], data=track['info'], metadata=metadata)
            for track in tracks
        ]

        if playlist:
            return Playlist(tracks, playlist, metadata=metadata)

        return tracks

    @overload
    async def search_track(
        self,
        query: str,
        *,
        source: Optional[Source] = ...,
        strict: bool = ...,
        resolve_playlists: Literal[True] = ...,
        prefer_selected_track: bool = ...,
        metadata: MetadataT = ...,
    ) -> Optional[Track[MetadataT]]:
        ...

    @overload
    async def search_track(
        self,
        query: str,
        *,
        source: Optional[Source] = ...,
        strict: bool = ...,
        resolve_playlists: Literal[False] = ...,
        prefer_selected_track: bool = ...,
        metadata: MetadataT = ...,
    ) -> Union[Playlist[MetadataT], Track[MetadataT]]:
        ...

    async def search_track(
        self,
        query: str,
        *,
        source: Optional[Source] = None,
        strict: bool = False,
        resolve_playlists: bool = False,
        prefer_selected_track: bool = True,
        metadata: MetadataT = _None,
    ) -> Union[Playlist[MetadataT], Track[MetadataT], None]:
        """|coro|

        Finds a track that matches the given query in the given source.

        Parameters
        ----------
        query: str
            The search query.
        source: Optional[:class:`.Source`]
            The source to search on.
            If no source is given then only URLs or specific identifiers can be passed as the query.
        strict: bool
            If ``False`` (the default), this will automatically ignore the source if a URL is passed.
            This is usually what you want.

            If ``True``, then the URL will be searched on the given source.
            This should only be used if you require the :attr:`.Track.source` to be consistent every time.
        resolve_playlists: bool
            Whether to return a track in the playlist if one was returned.
            If ``True``, then the track returned will never be a :class:`.Playlist` object, however it
            will have the chance of returning ``None`` if no tracks are in the playlist.

            Else, if a playlist is found, this will still return the :class:`.Playlist` object.

            Defaults to ``False``.
        prefer_selected_track: bool
            If set to ``True`` and a playlist is returned, then the :attr:`.Playlist.selected_track` will be returned.
            If there is no selected track, this will fall back to the first track in the playlist.

            Else, the first track will be returned.

            This parameter only works in conjunction with `resolve_playlists` set to ``True``.

            Defaults to ``True``.
        metadata
            The metadata to associate with the tracks and/or playlist.
            Metadata associated with playlists will be passed down to their child tracks.

            Could be useful for associating a requester with the track or playlist.
            This is optional and defaults to ``None``.

        Returns
        -------
        Union[:class:`.Playlist`, :class:`.Track`, None]
            The track or playlist that matches the query.

        Raises
        ------
        NoMatches
            No tracks were found with your query.
        LoadFailed
            The search query failed to load.
        """
        # noinspection PyTypeChecker
        result = await self.search_tracks(
            query,
            source=source,
            strict=strict,
            flatten_playlists=resolve_playlists and not prefer_selected_track,  # type: ignore
            limit=1,
            metadata=metadata,
        )

        if isinstance(result, list):
            try:
                return result[0]
            except IndexError:
                return None

        if prefer_selected_track and isinstance(result, Playlist):
            return result.selected_track or result.first

        return result

    async def fetch_track(self, id: str, *, metadata: MetadataT = _None) -> Track[MetadataT]:
        """|coro|

        Fetches and resolves a track given its track ID.

        Parameters
        ----------
        id: str
            The base 64 ID of the track to fetch.
        metadata
            The metadata to associate with the fetched track.

            Could be useful for associating a requester with the track.
            This is optional and defaults to ``None``.

        Returns
        -------
        :class:`.Track`
            The track that was fetched.

        Raises
        ------
        NotFound
            The track was not found.
        """
        response = await self.request('GET', 'decodetrack', track=id)
        return Track(id=id, data=response, metadata=metadata)

    async def fetch_tracks(
        self,
        ids: Iterable[str],
        *,
        atomic: bool = False,
        metadata: MetadataT = _None,
    ) -> List[Track[MetadataT]]:
        """|coro|

        Fetches and resolves multiple tracks given their IDs.

        Parameters
        ----------
        ids: Iterable[:class:`str`]
            An iterable (i.e. :py:class:`list`) of strings, each string being a base 64 ID
            which represents a track to be fetched.
        atomic: bool
            Whether to fetch each track individually. Defaults to ``False``.
            This can ensure that if any track fails, other tracks will still be resolved.
        metadata
            The metadata to associate with the fetched tracks.

            Could be useful for associating a requester with the tracks.
            This is optional and defaults to ``None``.

        Returns
        -------
        list[:class:`.Track`]
            The tracks that were fetched.

        Raises
        ------
        NotFound
            One or more of the tracks were not found.
            This error will pass silently if ``atomic`` is ``True``.
        """
        if atomic:
            result = []

            for id in ids:
                try:
                    result.append(await self.fetch_track(id, metadata=metadata))
                except NotFound:
                    pass

            return result

        response: List[Dict[str, Any]] = await self.request('POST', 'decodetracks', data={'tracks': list(ids)})
        return [Track(id=id, data=data, metadata=metadata) for id, data in zip(ids, response)]

    def __repr__(self) -> str:
        return f'<Node {self.identifier!r}>'

    def __del__(self) -> None:
        self._cleanup()
