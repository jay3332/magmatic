from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, ClassVar, Dict, Generic, List, Literal, Optional, Protocol, TYPE_CHECKING, TypeVar, Union

import discord
from aiohttp import ClientSession, ClientWebSocketResponse, WSMsgType, WSServerHandshakeError
from discord.backoff import ExponentialBackoff

from .enums import OpCode
from .errors import AuthorizationFailure, ConnectionFailure, HTTPException, HandshakeFailure, PlayerNotFound
from .player import Player
from .stats import Stats

if TYPE_CHECKING:
    from discord.abc import Snowflake

    RequestMethod = Literal['GET', 'POST', 'PUT', 'PATCH', 'DELETE']

ClientT = TypeVar('ClientT', bound=discord.Client)
JsonT = TypeVar('JsonT', bound=Union[Dict[str, Any], List[Any], Any])

__all__ = (
    'Node',
)

log: logging.Logger = logging.getLogger(__name__)


class JSONSerializer(Protocol[JsonT]):
    def loads(self, data: str) -> JsonT:
        ...

    def dumps(self, data: JsonT) -> str:
        ...


class ConnectionManager:
    """Manages the connection of a :class:`Node`.

    This is used internally.
    """

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
        node: Node,
    ) -> None:
        self.node: Node[Any] = node
        self.host: str = host
        self.port: int = port
        self.loop: asyncio.AbstractEventLoop = loop
        self.session: ClientSession = session or ClientSession()
        self.heartbeat_interval: float = heartbeat_interval

        self._password: str = password
        self._ws_protocol: str = 'http' if prefer_http else 'ws'
        self._http_protocol: str = 'https' if secure else 'http'

        if secure:
            self._ws_protocol += 's'

        self._ws: Optional[ClientWebSocketResponse] = None
        self._ws_resume_key: str = os.urandom(8).hex()
        self._listener: Optional[asyncio.Task] = None
        self._serializer: JSONSerializer[Dict[str, Any]] = serializer

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
            'Client-Name': 'magmatic/' + __version__,
            'Resume-Key': self._ws_resume_key,
        }

        if self._password:
            result['Authorization'] = self._password

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

        await self.send_resume()

    async def disconnect(self) -> None:
        """Disconnects the current connection from Lavalink."""
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
            stats = data['stats']
            self.node._stats = Stats(stats)

            log.debug(f'[Node {self.node.identifier!r}]: Updated stats: {stats!r}')
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

    async def listen(self) -> None:
        backoff = ExponentialBackoff(base=3)

        async for message in self._ws:
            if message.type is WSMsgType.CLOSED:
                log.debug(f'[Node {self.node.identifier!r}]: Connection closed')

                delay = backoff.delay()
                log.warning(f'[Node {self.node.identifier!r}]: Attempting reconnect in {delay} seconds')

                await asyncio.sleep(delay)
                await self.connect(reconnect=True)

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
            raise RuntimeError('no running websocket to send message to')

        raw = self._serializer.dumps(data)
        if isinstance(raw, bytes):
            raw = raw.decode('utf-8')

        await self._ws.send_str(raw)

    async def send_voice_server_update(self, *, guild_id: int, session_id: int, event: Dict[str, Any]) -> None:
        await self.send({
            'op': 'voiceUpdate',
            'guildId': guild_id,
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
            'guildId': guild_id,
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
            'guildId': guild_id,
        })

    async def send_pause(self, *, guild_id: int, pause: bool = True) -> None:
        await self.send({
            'op': 'pause',
            'guildId': guild_id,
            'pause': pause,
        })

    async def send_seek(self, *, guild_id: int, position: int) -> None:
        await self.send({
            'op': 'seek',
            'guildId': guild_id,
            'position': position,
        })

    async def send_volume(self, *, guild_id: int, volume: int) -> None:
        await self.send({
            'op': 'volume',
            'guildId': guild_id,
            'volume': volume,
        })

    async def send_destroy(self, *, guild_id: int) -> None:
        await self.send({
            'op': 'destroy',
            'guildId': guild_id,
        })

    async def send_resume(self) -> None:
        await self.send({
            'op': 'configureResuming',
            'key': self._ws_resume_key,
            'timeout': 60,
        })

    async def request(self, method: RequestMethod, endpoint: str, **params: Any) -> Dict[str, Any]:
        """|coro|

        Sends a request to an endpoint on Lavalink's REST API.

        Parameters
        ----------
        method: str
            The HTTP request method to use, e.g. ``'GET'``.
        endpoint: str
            The endpoint to send the request to.
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
        kwargs = dict(
            method=method,
            url=f'{self.http_url}/{endpoint}',
            headers={'Authorization': self._password},
            params=params,
        )

        for i in range(self.REQUEST_MAX_TRIES):
            async with self.session.request(**kwargs) as response:
                if not response.ok:
                    if i + 1 < self.REQUEST_MAX_TRIES:
                        delay = backoff.delay()
                        await asyncio.sleep(delay)

                    continue

                return await response.json(loads=self._serializer.loads)

        try:
            raise HTTPException(response)  # type: ignore
        except NameError:
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
        serializer: JSONSerializer[Dict[str, Any]] = json,
    ) -> None:
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
            serializer=serializer,
            node=self,
        )

        self._players: Dict[int, Player] = {}
        self._stats: Optional[Stats] = None

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        """:class:`asyncio.AbstractEventLoop`: The event loop associated with this node."""
        if self._loop is None:
            return self.bot.loop

        return self._loop

    @property
    def connection(self) -> ConnectionManager:
        """:class:`ConnectionManager`: The :class:`ConnectionManager` managing this node's connection with Lavalink."""
        return self._connection

    @property
    def players(self) -> List[Player]:
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

    def get_player(self, guild: Snowflake, *, fail_if_not_exists: bool = False) -> Player:
        """Returns the :class:`.Player` associated with the given guild.

        If ``fail_if_not_exists`` is ``False`` and the player does not exist, one is created.

        Parameters
        ----------
        guild: :class:`discord.abc.Snowflake`
            The guild to get the player for.

            Could be a :class:`snowflake <discord.abc.Snowflake>`-like object,
            such as :class:`discord.Object`, if you cannot resolve the full guild object yet.
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

            self._players[guild.id] = Player(node=self, guild=guild)

        return self._players[guild.id]

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
        await self.connection.connect()

    async def disconnect(self) -> None:
        """|coro|

        Disconnects this node from Lavalink and clears any data associated with it.
        """
        log.info(f'[Node {self.identifier!r}]: Disconnecting...')
        await self.connection.disconnect()

    async def destroy(self) -> None:
        """|coro|

        Disconnects and removes this node from its associated :class:`.NodePool`.
        """
        log.info(f'[Node {self.identifier!r}]: Destroying node...')

        await self.disconnect()

    async def request(self, method: RequestMethod, endpoint: str, **params: Any) -> Dict[str, Any]:
        """|coro|

        Sends a request to an endpoint on Lavalink's REST API.

        Parameters
        ----------
        method: str
            The HTTP request method to use, e.g. ``'GET'``.
        endpoint: str
            The endpoint to send the request to.
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
        return await self.connection.request(method, endpoint, **params)

    def __repr__(self) -> str:
        return f'<Node {self.identifier!r}>'
