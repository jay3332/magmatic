from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aiohttp import ClientResponse

    from .node import Node

__all__ = (
    'MagmaticException',
    'HTTPException',
    'ConnectionFailure',
    'HandshakeFailure',
    'AuthorizationFailure',
)


class MagmaticException(Exception):
    """The base exception for all errors raised by Magmatic."""


class HTTPException(MagmaticException):
    """Raised when an error occured requesting to Lavalink's REST API.

    Attributes
    ----------
    response: :class:`aiohttp.ClientResponse`
        The aiohttp response object received from Lavalink.
    """

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

    def __init__(self, node: Node) -> None:
        self.node: Node = node

        super().__init__(f'Invalid authorization passed for node {node.identifier!r}')
