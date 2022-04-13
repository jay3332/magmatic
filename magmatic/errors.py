from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .node import Node

__all__ = (
    'MagmaticException',
    'ConnectionFailure',
    'AuthorizationFailure',
)


class MagmaticException(Exception):
    """The base exception for all errors raised by Magmatic."""


class ConnectionFailure(MagmaticException):
    """Raised when an error occurs during connection."""

    def __init__(self, node: Node, error: Exception) -> None:
        self.node: Node = node
        self.error: Exception = error

        super().__init__(f'Failed connecting to node {node.identifier!r}: {error}')


class HandshakeFailure(MagmaticException):
    """Raised when an error occurs during handshake."""


class AuthorizationFailure(MagmaticException):
    """Raised when an authorization failure occurs for a node."""

    def __init__(self, node: Node) -> None:
        self.node: Node = node

        super().__init__(f'Invalid authorization passed for node {node.identifier!r}')
