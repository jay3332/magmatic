from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict, Optional, TYPE_CHECKING, TypeVar, Union

from aiohttp import ClientSession, ClientWebSocketResponse, WSMsgType, WSServerHandshakeError
from discord.backoff import ExponentialBackoff

from magmatic.enums import OpCode
from magmatic.errors import AuthorizationFailure, ConnectionFailure, HandshakeFailure

if TYPE_CHECKING:
    from discord import Client

    ClientT = TypeVar('ClientT', bound=Client)

__all__ = (
    'Node',
)

log: logging.Logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages the connection of a :class:`Node`.

    This is used internally.
    """

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
        node: Node,
    ) -> None:
        self.node: Node = node
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

    @property
    def origin(self) -> str:
        """The base URI origin to use when connecting or requesting to Lavalink."""
        return f'{self.host}:{self.port}'

    @property
    def url(self) -> str:
        """The URL to use when connecting to the websocket."""
        return f'{self._ws_protocol}://{self.origin}'

    @property
    def http_url(self) -> str:
        """The URL to use when requesting an endpoint from the HTTP REST API."""
        return f'{self._http_protocol}://{self.origin}'

    @property
    def headers(self) -> Dict[str, str]:
        """The headers to use when making a request to Lavalink."""
        result = {
            'User-Id': str(self.node.bot.user.id),
            'Client-Name': 'magmatic',
            'Resume-Key': self._ws_resume_key,
        }

        if self._password:
            result['Authorization'] = self._password

        return result

    def is_connected(self) -> bool:
        """Whether the websocket is connected to Lavalink."""
        return self._ws is not None and not self._ws.closed

    async def connect(self, *, reconnect: bool = True) -> None:
        """Connects to Lavalink."""
        if self.is_connected():
            if not reconnect:
                return

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
        self._listener = self.loop.create_task(self.listen())

    async def disconnect(self) -> None:
        """Disconnects the current connection from Lavalink."""
        if self._listener and not self._listener.done():
            self._listener.cancel()

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
                    '[Node {self.node.identifier!r}]: Internal error occurred in Lavalink; terminating connection.',
                )

                self._listener.cancel()
                await self.disconnect()
                return

            self.loop.create_task(self.handle_message(message.json()))
    
    async def send(self, data: Dict[str, Any]) -> None:
        """Sends a message to Lavalink server via websocket."""
        await self._ws.send_json(data)

class Node:
    """Represents a client which interfaces around a Lavalink node.

    These are not to be constructed manually, rather they should be created via
    :func:`.create_node` or :func:`.start_node`.

    Attributes
    ----------
    bot: :class:`discord.Client`
        The discord.py client/bot instance associated with this node.
    """

    def __init__(
        self,
        *,
        bot: ClientT,
        host: str = '127.0.0.1',
        port: Union[int, str] = 3030,
        password: Optional[str] = None,
        region: Optional[str] = None,
        identifier: Optional[str] = None,
        session: Optional[ClientSession] = None,
        loop: Optional[asyncio.AbstractEventLoop] = None,
        prefer_http: bool = False,
    ) -> None:
        self.bot: ClientT = bot
        self.identifier: str = identifier or os.urandom(8).hex()
        self.region: Optional[str] = region

        self._loop: Optional[asyncio.AbstractEventLoop] = loop
        self._connection: Optional[ConnectionManager] = ConnectionManager(
            host=host,
            port=port,
            password=password,
            loop=self.loop,
            session=session,
            prefer_http=prefer_http,
            node=self
        )

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        """The event loop associated with this node."""
        if self._loop is None:
            return self.bot.loop

        return self._loop

    async def connect(self) -> None:
        """Connects this node to Lavalink."""
        await self._connection.connect()

    async def disconnect(self) -> None:
        """Disconnects this node from Lavalink and clears any data associated with it."""
        log.info(f'[Node {self.identifier!r}]: Disconnecting...')
        await self._connection.disconnect()

    async def destroy(self) -> None:
        """Disconnects and removes this node from its associated :class:`.NodePool`."""
        log.info(f'[Node {self.identifier!r}]: Destroying node...')

        await self.disconnect()

    async def send_voice_server_update(self, guild_id: int, session_id: int, event: Dict[str, Any]) -> None:
        """Sends a voice server update to Lavalink."""
        await self._connection.send({
            'op': 'voiceUpdate',
            'guildId': guild_id,
            'sessionId': session_id,
            'event': event,
        })
    
    async def send_play_track(
        self, 
        guild_id: int, 
        track: str,
        start_time: int = 0, 
        end_time: int | None = None, 
        volume: int | None = None, 
        no_replace: bool = False, 
        pause: bool = False
    ) -> None:
        """
        Sends a play track request to Lavalink.
        """
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
        
        await self._connection.send(data)
    
    async def send_stop(self, guild_id: int) -> None:
        """
        Sends a stop player request to Lavalink.
        """
        await self._connection.send({
            'op': 'stop',
            'guildId': guild_id,
        })
    
    async def send_pause(self, guild_id: int, pause: bool = True) -> None:
        """
        Sends a pause player request to Lavalink.
        """
        await self._connection.send({
            'op': 'pause',
            'guildId': guild_id,
            'pause': pause,
        })
    
    async def send_seek(self, guild_id: int, position: int) -> None:
        """
        Sends a seek player request to Lavalink.
        """
        await self._connection.send({
            'op': 'seek',
            'guildId': guild_id,
            'position': position,
        })
    
    async def send_set_volume(self, guild_id: int, volume: int) -> None:
        """
        Sends a set volume request to Lavalink.
        """
        await self._connection.send({
            'op': 'volume',
            'guildId': guild_id,
            'volume': volume,
        })
    
    async def send_destroy(self, guild_id: int) -> None:
        """
        Sends a destroy player request to Lavalink.
        """
        await self._connection.send({
            'op': 'destroy',
            'guildId': guild_id,
        })

    def __repr__(self) -> str:
        return f'<Node {self.identifier!r}>'
