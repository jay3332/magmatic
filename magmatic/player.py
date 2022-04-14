from __future__ import annotations

import logging
from typing import Any, Dict, Generic, Optional, TYPE_CHECKING, Union

import discord
from discord import VoiceProtocol
from discord.utils import MISSING

if TYPE_CHECKING:
    from discord.abc import Snowflake
    from discord.channel import VocalGuildChannel
    from discord.types.voice import GuildVoiceState, VoiceServerUpdate

    from .node import ClientT, Node

__all__ = (
    'Player',
)

log: logging.Logger = logging.getLogger(__name__)


class Player(VoiceProtocol, Generic[ClientT]):
    """Represents an audio player on a specific guild.

    This class can be inherited to allow custom behaviors, although this class
    is not meant to be constructed manually.

    See :meth:`.Node.get_player` or :func:`get_player` for retrieving the player object itself.

    This class inherits from :class:`discord.VoiceProtocol`. If this is directly constructed
    (likely using the ``cls`` kwarg in :meth:`Connectable.connect <discord.abc.Connectable.connect>`),
    a node will be pulled from the :ref:`DefaultNodePool` and the player will be added to it.

    If you would like this player to be on a specific node (which in consequence could also be in a sepcific NodePool),
    see :meth:`.Node.connect` (or the two get_player methods listed above if you don't want to immediately connect).

    Attributes
    ----------
    node: :class:`.Node`
        The node that the player is currently playing on.
    guild: :class:`discord.abc.Snowflake`
        The guild associated with this player.
    channel: Optional[Union[:class:`discord.VoiceChannel`, :class:`discord.StageChannel`]]
        The current voice channel the player is in. ``None`` if the player is not connected to a voice channel.
    """

    client: ClientT
    channel: VocalGuildChannel

    def __init__(
        self,
        client: ClientT = MISSING,
        channel: VocalGuildChannel = MISSING,
        /,
        *,
        node: Node = MISSING,
        guild: Snowflake = MISSING,
    ) -> None:
        if client is not MISSING and channel is not MISSING:
            if node is MISSING:
                from .pool import DefaultNodePool

                node = DefaultNodePool.get_node()

            if guild is MISSING:
                guild = channel.guild

        elif node is not MISSING and guild is not MISSING:
            client = node.bot
        else:
            raise TypeError(f'{self.__class__.__name__} constructor requires both a node and guild.')

        self.node: Node[ClientT] = node
        self.guild: Snowflake = guild

        self._voice_server_data: Dict[str, Any] = {}

        super().__init__(client, channel)

    def _upgrade_guild(self) -> None:
        if isinstance(self.guild, discord.Guild):
            return

        if guild := self.client.get_guild(self.guild.id):
            self.guild = guild
            return

        # TODO: destroy the player - most likely bot was kicked during the connection process, which is super rare.
        raise RuntimeError(
            f'Could not upgrade partial guild with ID {self.guild.id} into a full Guild object. '
            'Try passing in the actual guild object instead.',
        )

    @property
    def bot(self) -> ClientT:
        """:class:`discord.Client`: The discord.py client/bot object associated with this player."""
        return self.client

    @property
    def guild_id(self) -> int:
        """:class:`int`: The ID of the guild associated with this player."""
        return self.guild.id

    @property
    def channel_id(self) -> Optional[int]:
        """Optional[:class:`int`]: The ID of the voice channel this player is connected to.

        This is ``None`` if the player is not connected to a voice channel.
        """
        return self.channel and self.channel.id

    def is_connected(self) -> bool:
        """:class:`bool`: Returns whether the player is connected to a voice channel."""
        return self.channel is not None

    async def _update_voice_data(self, **data: Any) -> None:
        log.debug(f'[Node {self.node.identifier!r}] Updating voice data for player {self!r}')

        if 'session_id' not in self._voice_server_data or 'event' not in self._voice_server_data:
            return

        await self.node.connection.send_voice_server_update(
            guild_id=self.guild_id,
            **self._voice_server_data,
            **data,
        )

    async def on_voice_server_update(self, data: VoiceServerUpdate) -> None:
        self._voice_server_data['event'] = data

        await self._update_voice_data()

    async def on_voice_state_update(self, data: GuildVoiceState) -> None:
        self._voice_server_data['session_id'] = data['session_id']

        if not data['channel_id']:
            # Disconnect
            self._voice_server_data.clear()
            return

        channel_id = int(data['channel_id'])
        if channel_id != self.channel_id:
            # Moved channels
            self.channel = self.client.get_channel(channel_id)

        await self._update_voice_data(event=data)

    async def connect(self, channel: Optional[VocalGuildChannel] = None, *, timeout: float = MISSING, reconnect: bool = MISSING) -> None:
        """|coro|

        Connects to the voice channel associated with this player. This is usually called internally.

        Parameters
        ----------
        channel: Optional[Union[:class:`discord.VoiceChannel`, :class:`discord.StageChannel`]]
            The voice channel to connect to.
        """
        if channel is not None:
            self.channel = channel

        self._upgrade_guild()
        assert isinstance(self.guild, discord.Guild)

        log.debug(f'[Node {self.node.identifier!r}] Connecting to voice channel with ID {self.channel_id!r}')
        await self.guild.change_voice_state(channel=self.channel)

    def __repr__(self) -> str:
        return f'<Player node={self.node.identifier!r} guild_id={self.guild_id} channel_id={self.channel_id}>'
