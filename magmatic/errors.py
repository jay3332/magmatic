from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from discord.abc import Snowflake

if TYPE_CHECKING:
    from aiohttp import ClientResponse

    from .enums import ErrorSeverity, Source
    from .node import Node
    from .player import Player
    from .pool import NodePool

__all__ = (
    'MagmaticException',
    'HTTPException',
    'ConnectionFailure',
    'HandshakeFailure',
    'AuthorizationFailure',
    'NoMatchingNodes',
    'NoAvailableNodes',
    'NodeConflict',
    'PlayerNotFound',
    'NoMatches',
    'LoadFailed',
    'NotConnected',
)


class MagmaticException(Exception):
    """The base exception for all errors raised by Magmatic."""

    __slots__ = ()


class HTTPException(MagmaticException):
    """Raised when an error occured requesting to Lavalink's REST API.

    Attributes
    ----------
    response: :class:`aiohttp.ClientResponse`
        The aiohttp response object received from Lavalink.
    """

    __slots__ = ('response',)

    def __init__(self, response: ClientResponse) -> None:
        self.response: ClientResponse = response

    @property
    def status(self) -> int:
        """:class:`int`: The HTTP status code of the response."""
        return self.response.status


class ConnectionFailure(MagmaticException):
    """Raised when an error occurs during connection.

    Attributes
    ----------
    node: :class:`.Node`
        The node that failed to connect.
    error: :class:`Exception`
        The exception that was raised.
    """

    __slots__ = ('node', 'error')

    def __init__(self, node: Node, error: Exception) -> None:
        self.node: Node = node
        self.error: Exception = error

        super().__init__(f'Failed connecting to node {node.identifier!r}: {error}')


class HandshakeFailure(MagmaticException):
    """Raised when an error occurs during handshake."""


class AuthorizationFailure(MagmaticException):
    """Raised when an authorization failure occurs for a node.

    Attributes
    ----------
    node: :class:`.Node`
        The node that failed to authorize.
    """

    __slots__ = ('node',)

    def __init__(self, node: Node) -> None:
        self.node: Node = node

        super().__init__(f'Invalid authorization passed for node {node.identifier!r}')


class NodeConflict(MagmaticException):
    """Raised when there is a conflict between node identifiers.

    Attributes
    ----------
    pool: :class:`.NodePool`
        The node pool that contains the conflicting nodes.
    identifier: :class:`str`
        The identifier of the conflicting node.
    """

    __slots__ = ('pool', 'identifier')

    def __init__(self, pool: NodePool, identifier: str) -> None:
        self.pool: NodePool = pool
        self.identifier: str = identifier

        super().__init__(f'Node identifier {identifier!r} is already in use.')


class NoAvailableNodes(MagmaticException):
    """Raised when there are no available nodes in a given :class:`.NodePool`.

    Attributes
    ----------
    pool: :class:`.NodePool`
        The node pool that contains no nodes.
    """

    __slots__ = ('pool',)

    def __init__(self, pool: NodePool) -> None:
        self.pool: NodePool = pool

        super().__init__('No available nodes on this pool.')


class NoMatchingNodes(MagmaticException):
    """Raised when there are no node matches.

    Attributes
    ----------
    pool: :class:`.NodePool`
        The node pool that matches could not be found from.
    identifier: Optional[:class:`str`]
        The identifier attempted to be matched. Could be ``None`` if no identifier was provided.
    region: Optional[:class:`str`]
        The region attempted to be matched. Could be ``None`` if no region was provided.
    """

    __slots__ = ('pool', 'identifier', 'region')

    def __init__(self, pool: NodePool, identifier: Optional[str], region: Optional[str]) -> None:
        self.pool: NodePool = pool
        self.identifier: Optional[str] = identifier
        self.region: Optional[str] = region

        entities = []
        if identifier is not None:
            entities.append(f'identifier {identifier!r}')

        if region is not None:
            entities.append(f'voice region {region!r}')

        super().__init__(f'No node with {" and ".join(entities)} could be found in this pool.')


class PlayerNotFound(MagmaticException):
    """Raised when a :class:`.Player` is not found via :meth:`.Node.get_player`.

    Attributes
    ----------
    node: :class:`.Node`
        The node in which the player was not found.
    guild: :class:`discord.abc.Snowflake`
        The guild/snowflake object passed into :meth:`.Node.get_player`.
    """

    __slots__ = ('node', 'guild')

    def __init__(self, node: Node, guild: Snowflake) -> None:
        self.node: Node = node
        self.guild: Snowflake = guild

        super().__init__(f'Player for guild {guild!r} not found')


class NoMatches(MagmaticException):
    """Raised when there are no matches for a search query or source.

    Attributes
    ----------
    node: :class:`.Node`
        The Lavalink node that could not find any matches
    query: str
        The query that could not be matched
    source: Optional[:class:`.Source`]
        The source that was given. Could be ``None`` if no source was given.
    """

    __slots__ = ('node', 'query', 'source')

    def __init__(self, node: Node, query: str, source: Optional[Source]) -> None:
        self.node: Node = node
        self.query: str = query
        self.source: Optional[Source] = source

        super().__init__(f'No matches found for query {query!r} (Source: {source and source.name})')


class LoadFailed(MagmaticException):
    """Raised when loading tracks while searching fails.

    Attributes
    ----------
    node: :class:`.Node`
        The Lavalink node that failed loading tracks
    message: str
        The error message provided by Lavalink
    severity: :class:`.ErrorSeverity`
        The error severity of the error provided by Lavalink
    """

    __slots__ = ('node', 'message', 'severity')

    def __init__(self, node: Node, message: str, severity: ErrorSeverity) -> None:
        self.node: Node = node
        self.message: str = message
        self.severity: ErrorSeverity = severity

        super().__init__(f'Could not load tracks: {message} (Severity: {severity.name!r})')


class NotConnected(MagmaticException):
    """Raised when a player attempted to do an action that required a connection,
    but the player was not connected.

    Attributes
    ----------
    player: :class:`.Player`
        The player that was not connected.
    """

    __slots__ = ('player',)

    def __init__(self, player: Player) -> None:
        self.player: Player = player

        super().__init__(f'Player {player!r} (on node {player.node.identifier!r}) is not connected')
