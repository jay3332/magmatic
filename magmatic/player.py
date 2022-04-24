from __future__ import annotations

import logging
import time
from typing import Any, Awaitable, Callable, Dict, Generic, Optional, TYPE_CHECKING, Type, TypeVar, Union

import discord
from discord import VoiceProtocol
from discord.utils import MISSING

from .errors import NotConnected
from .filters import BaseFilter, Equalizer, FilterSink

if TYPE_CHECKING:
    from discord.abc import Snowflake
    from discord.channel import VocalGuildChannel
    from discord.types.voice import GuildVoiceState, VoiceServerUpdate

    from .events import (
        BaseEvent,
        TrackStartEvent,
        TrackEndEvent,
        TrackExceptionEvent,
        TrackStuckEvent,
        WebSocketCloseEvent,
    )
    from .node import Node
    from .track import Track

ClientT = TypeVar('ClientT', bound=discord.Client)

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

    if TYPE_CHECKING:
        async def on_track_start(self, event: TrackStartEvent) -> None:
            ...

        async def on_track_end(self, event: TrackEndEvent) -> None:
            ...

        async def on_track_exception(self, event: TrackExceptionEvent) -> None:
            ...

        async def on_track_stuck(self, event: TrackStuckEvent) -> None:
            ...

        async def on_websocket_close(self, event: WebSocketCloseEvent) -> None:
            ...

    def __init__(
        self,
        client: ClientT = MISSING,
        channel: VocalGuildChannel = MISSING,
        /,
        *,
        node: Node[ClientT] = MISSING,
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

        self._track: Optional[Track] = None
        self._paused: bool = False
        self._volume: int = 100
        self._filters: FilterSink = MISSING  # lazily initialized

        self._previous_update_time: float = 0
        self._previous_position: float = 0
        self._voice_server_data: Dict[str, Any] = {}

        super().__init__(client, channel)

    def _upgrade_guild(self) -> None:
        if isinstance(self.guild, discord.Guild):
            return

        if self.channel is not MISSING:
            self.guild = self.channel.guild
            return

        if guild := self.client.get_guild(self.guild.id):
            self.guild = guild
            return

        # TODO: destroy the player - most likely bot was kicked during the connection process, which is super rare.
        raise RuntimeError(
            f'Could not upgrade partial guild with ID {self.guild.id} into a full Guild object. '
            'Try passing in the actual guild object instead, or enabling guild intents.',
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

    @property
    def voice(self) -> Optional[discord.VoiceState]:
        """Optional[:class:`discord.VoiceState`]: The voice state associated with this player.

        This is ``None`` if the player is not connected to a voice channel.
        This is also ``None`` if :attr:`discord.Intents.voice_states` is not enabled.
        """
        return self.guild.me.voice if isinstance(self.guild, discord.Guild) else None

    @property
    def track(self) -> Optional[Track]:
        """Optional[:class:`.Track`]: The currently playing track. ``None`` if no track is currently playing."""
        return self._track

    @property
    def position(self) -> float:
        """float: The seek position of the player in seconds.

        In simpler terms, how many seconds the current track has been playing for.
        """
        if not self.is_playing():
            return 0

        assert self._track is not None

        if self.is_paused():
            return min(self._previous_position, self._track.duration)

        # We must use time.time() here since we are comparing Unix epochs.
        offset = time.time() - self._previous_update_time
        return min(self._previous_position + offset, self._track.duration)

    @property
    def volume(self) -> int:
        """:class:`int`: The current volume of the player."""
        return self._volume

    @property
    def filters(self) -> FilterSink:
        """:class:`.FilterSink`: The filters currently applied to the player.

        View documentation on :class:`.FilterSink` for more information on using filters.
        """
        if self._filters is MISSING:
            self._filters = FilterSink()

        return self._filters

    @property
    def equalizer(self) -> Optional[Equalizer]:
        """:class:`.Equalizer`: The equalizer currently applied to the player's :class:`.FilterSink`.

        This shortcut exists for backwards compatibility purposes. This will be ``None`` if no equalizer is applied.

        Additionally, note that any change in the equalizer made using this property will not be applied
        until :meth:`.Player.apply_filters` is called.
        """
        return self.filters.equalizer

    def is_connected(self) -> bool:
        """:class:`bool`: Returns whether the player is connected to a voice channel."""
        return (
            self.channel is not MISSING
            and isinstance(self.guild, discord.Guild)
            and self.voice is not None
            and self.voice.channel is not None
        )

    def is_playing(self) -> bool:
        """:class:`bool`: Returns whether the player is currently playing a track."""
        return self.is_connected() and self._track is not None

    def is_self_muted(self) -> bool:
        """:class:`bool`: Returns whether the player's voice state is self-muted."""
        return self.voice is not None and self.voice.self_mute

    def is_self_deafened(self) -> bool:
        """:class:`bool`: Returns whether the player's voice state is self-deafened."""
        return self.voice is not None and self.voice.self_deaf

    def is_paused(self) -> bool:
        """:class:`bool`: Returns whether the player is paused."""
        return self._paused

    async def _update_voice_data(self, **data: Any) -> None:
        log.debug(f'[Node {self.node.identifier!r}] Updating voice data for player {self!r}')

        if 'session_id' not in self._voice_server_data or 'event' not in self._voice_server_data:
            return

        await self.node.connection.send_voice_server_update(
            guild_id=self.guild_id,
            **self._voice_server_data,
            **data,
        )

    def _reset_state(self) -> None:
        self._previous_update_time = self._previous_position = 0

    def _update_state(self, data: Dict[str, Any]) -> None:
        self._previous_update_time = data['time'] / 1000
        self._previous_position = data.get('position', 0) / 1000

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
            channel = self.client.get_channel(channel_id)
            assert isinstance(channel, VocalGuildChannel)
            self.channel = channel

        await self._update_voice_data(event=data)

    def _inject_voice_client(self) -> None:
        if self.channel is MISSING:
            raise RuntimeError('no channel to join')

        key_id, _ = self.channel._get_voice_client_key()
        state = self.channel._state

        if state._get_voice_client(key_id):
            return

        state._add_voice_client(key_id, self)

    async def connect(
        self,
        channel: Optional[VocalGuildChannel] = None,
        *,
        timeout: float = 60.0,
        reconnect: bool = False,
        self_mute: bool = False,
        self_deaf: bool = False,
    ) -> None:
        """|coro|

        Connects to the voice channel associated with this player. This is usually called internally.

        Parameters
        ----------
        channel: Optional[Union[:class:`discord.VoiceChannel`, :class:`discord.StageChannel`]]
            The voice channel to connect to.
        timeout: :class:`float`
            The timeout in seconds to wait for connection. Defaults to 60 seconds.
        reconnect: :class:`bool`
            Whether to automatically attempt reconnecting if a part of the handshake fails
            or the gateway goes down.

            Defaults to ``False``.
        self_mute: :class:`bool`
            Whether to self-mute upon joining the channel. Defaults to ``False``.
        self_deaf: :class:`bool`
            Whether to self-deafen upon connecting. Defaults to ``False``.

        Raises
        ------
        RuntimeError
            The given guild was not a complete :class:`discord.Guild` object,
            and the guild could not be resolved upon connection.

            If this happens, try passing in the actual guild object instead, or enabling guild intents.
        """
        if channel is not None:
            if self.channel == channel and self.is_connected():
                return

            self.channel = channel

        self._upgrade_guild()
        assert isinstance(self.guild, discord.Guild)

        self._inject_voice_client()
        log.debug(f'[Node {self.node.identifier!r}] Connecting to voice channel with ID {self.channel_id!r}')
        await self.guild.change_voice_state(channel=self.channel, self_deaf=self_deaf, self_mute=self_mute)

    async def reconnect(self) -> None:
        """|coro|

        Disconnects and reconnects to the voice channel associated with this player.

        This method takes no arguments as all this should do is reconnect the player to its
        original state.
        """
        log.debug(f'[Node {self.node.identifier!r}] Reconnecting to voice channel with ID {self.channel_id!r}')

        await self.disconnect(force=True, destroy=False)
        await self.connect(self.channel, self_deaf=self.is_self_deafened(), self_mute=self.is_self_muted())

    async def disconnect(self, *, force: bool = False, destroy: bool = True) -> None:
        """|coro|

        Disconnects from the voice channel associated with this player.

        Parameters
        ----------
        force: :class:`bool`
            Whether to force disconnection.
        destroy: :class:`bool`
            Whether to destroy the player. Defaults to ``True``.

            If you would like the player state to persist after disconnection, set this to ``False``.

        Raises
        ------
        RuntimeError
            The given guild was not a complete :class:`discord.Guild` object,
            and the guild could not be resolved upon connection.

            If this happens, try passing in the actual guild object instead, or enabling guild intents.
        """
        if not self.is_connected():
            return

        try:
            self._upgrade_guild()
            assert isinstance(self.guild, discord.Guild)

            log.debug(f'[Node {self.node.identifier!r}] Disconnecting from voice channel with ID {self.channel_id!r}')
            await self.guild.change_voice_state(channel=None)
        finally:
            if destroy:
                await self.destroy(disconnect=False)
            else:
                # Clean-up the voice state regardless
                self.cleanup()

    async def destroy(self, *, disconnect: bool = True) -> None:
        """|coro|

        Destroys the player and cleans up any associated resources.

        Parameters
        ----------
        disconnect: :class:`bool`
            Whether to attempt to disconnect from voice. Defaults to ``True``.
        """
        try:
            if disconnect:
                await self.disconnect(force=True, destroy=False)
        finally:
            log.debug(f'[Node {self.node.identifier!r}] Destroying player with guild ID {self.guild_id}')
            await self.node.connection.send_destroy(guild_id=self.guild_id)

            self.node._players.pop(self.guild_id, None)
            self.cleanup()

    async def play(
        self,
        track: Track,
        *,
        start: Optional[float] = None,
        end: Optional[float] = None,
        volume: Optional[int] = None,
        replace: bool = True,
        pause: bool = False,
    ) -> None:
        """|coro|

        Starts playing the given track.

        Parameters
        ----------
        track: :class:`.Track`
            The track to start playing.
        start: Optional[:class:`float`]
            The time at which to start playing the track in seconds.
            Leave blank to start playing the beginning of the track.
        end: Optional[:class:`float`]
            The time at which to stop playing the track in seconds.
            Leave blank to play the track through completely.
        volume: Optional[:class:`int`]
            The volume at which to play the track. Must be between 0 and 1000.
            Leave blank to play at the current volume.
        replace: bool
            Whether to halt playing the current playing track is a track is currently playing.
            If set to ``False``, this method will silently do nothing if there is already audio playnig.

            Defaults to ``True``.
        pause: bool
            Whether to pause the track upon playing. Defaults to ``False``

        Raises
        ------
        NotConnected
            The player is not connected to a voice channel.
        ValueError
            - The given volume is not between 0 and 1000.
            - The given start time is below 0.
            - The given end time is less than the start time.
        """
        if not self.is_connected():
            raise NotConnected(self)

        if replace or not self.is_playing():
            self._reset_state()
            self._paused = False

        if start is not None:
            if start < 0:
                raise ValueError('start time must be greater than 0')

            if end is not None and start < end:
                raise ValueError('start must be greater than end')

        if volume is not None:
            if not 0 <= volume <= 1000:
                raise ValueError('volume must be between 0 and 1000')

            self._volume = volume

        await self.node.connection.send_play_track(
            guild_id=self.guild_id,
            track=track.id,
            start_time=int((start or 0) * 1000),
            end_time=int(end * 1000) if end is not None else None,
            volume=volume,
            no_replace=not replace,
            pause=pause,
        )

        log.debug(f'[Node {self.node.identifier!r}] Playing track {track!r} in guild ID {self.guild_id}')

        # This should not be handled manually; it is more reliable to listen for track_end followed by track_start.
        # However, the way this is designed right now will cause track metadata to be lost, and we don't want that.
        # In the future, we can possibly cache tracks by their ID which will resolve this issue
        if not replace and self.is_playing():
            return

        self._track = track

    async def seek(self, position: float) -> None:
        """|coro|

        Seeks to the given position (in seconds) in the current track.

        Parameters
        ----------
        position: float
            The position, in seconds, of where to seek to.
        """
        log.debug(f'[Node {self.node.identifier!r}] Seeking to {position}s in guild ID {self.guild_id}')
        await self.node.connection.send_seek(guild_id=self.guild_id, position=int(position * 1000))

    async def stop(self) -> None:
        """|coro|

        Stops the current playing track.
        """
        log.debug(f'[Node {self.node.identifier!r}] Stopping track in guild ID {self.guild_id}')

        await self.node.connection.send_stop(guild_id=self.guild_id)
        self._track = None

    # This following three methods are really similar to Player.connect and themselves;
    # we could possibly merge them in the future.
    async def move_to(self, channel: VocalGuildChannel) -> None:
        """|coro|

        Moves the player to the given voice channel.

        Parameters
        ----------
        channel: Union[:class:`discord.VoiceChannel`, :class:`discord.StageChannel`]
            The channel to move to.

        Raises
        ------
        RuntimeError
            The given guild was not a complete :class:`discord.Guild` object,
            and the guild could not be resolved upon connection.

            If this happens, try passing in the actual guild object instead, or enabling guild intents.
        """
        if not self.is_connected():
            return await self.connect(channel=channel)

        if self.channel == channel:
            return

        self._upgrade_guild()
        assert isinstance(self.guild, discord.Guild)

        log.debug(f'[Node {self.node.identifier!r}] Moving player to voice channel with ID {channel.id!r}')

        self.channel = channel
        await self.guild.change_voice_state(
            channel=self.channel,
            self_deaf=self.is_self_deafened(),
            self_mute=self.is_self_muted(),
        )

    async def set_deafen(self, deafen: bool) -> None:
        """|coro|

        Sets the self-deafened state of the player's voice state.

        Parameters
        ----------
        deafen: :class:`bool`
            Whether the player's voice state should be deafened.
        """
        if not self.is_connected():
            return

        self._upgrade_guild()
        assert isinstance(self.guild, discord.Guild)

        log.debug(f'[Node {self.node.identifier!r}] Setting deafen state to {deafen!r}')
        await self.guild.change_voice_state(
            channel=self.channel,
            self_deaf=deafen,
            self_mute=self.is_self_muted(),
        )

    async def set_mute(self, mute: bool) -> None:
        """|coro|

        Sets the self-muted state of the player's voice state.

        Parameters
        ----------
        mute: :class:`bool`
            Whether the player's voice state should be muted.
        """
        if not self.is_connected():
            return

        self._upgrade_guild()
        assert isinstance(self.guild, discord.Guild)

        log.debug(f'[Node {self.node.identifier!r}] Setting mute state to {mute!r}')
        await self.guild.change_voice_state(
            channel=self.channel,
            self_deaf=self.is_self_deafened(),
            self_mute=mute,
        )

    async def set_pause(self, pause: bool) -> None:
        """|coro|

        Sets the paused state of the player.

        Parameters
        ----------
        pause: :class:`bool`
            The new paused state of the player. Set to ``True`` to pause; ``False`` to resume.
        """
        await self.node.connection.send_pause(guild_id=self.guild_id, pause=pause)
        self._paused = pause

        log.debug(f'[Node {self.node.identifier!r}] Paused state of player with guild ID {self.guild_id} set to {pause}')

    async def toggle_pause(self) -> None:
        """|coro|

        Sets the paused state of the player to ``True`` if it is currently ``False``,
        else ``False`` if it is currently ``True``.
        """
        await self.set_pause(not self._paused)

    async def pause(self) -> None:
        """|coro|

        Sets the player's paused state to ``True``.
        """
        await self.set_pause(True)

    async def resume(self) -> None:
        """|coro|

        Sets the player's paused state to ``False``.
        """
        await self.set_pause(False)

    async def set_volume(self, volume: int) -> None:
        """|coro|

        Sets the volume of the player.

        Parameters
        ----------
        volume: :class:`int`
            The new volume of the player, in percent. Must be a whole number between ``0`` and ``1000``.

        Raises
        ------
        ValueError
            The given volume was not between ``0`` and ``1000``.
        """
        if not 0 <= volume <= 1000:
            raise ValueError('Volume must be between 0 and 1000.')

        await self.node.connection.send_volume(guild_id=self.guild_id, volume=volume)
        self._volume = volume

        log.debug(f'[Node {self.node.identifier!r}] Volume of player with guild ID {self.guild_id} set to {volume}')

    async def apply_filters(self) -> None:
        """|coro|

        Applies the filters from :attr:`.Player.filters` to the player.
        """
        if not self._filters:
            return

        await self.node.connection.send_filters(guild_id=self.guild_id, filters=self._filters.to_dict())
        log.debug(f'[Node {self.node.identifier!r}] Applied filters of player with guild ID {self.guild_id}')

    async def add_filters(self, *filters: BaseFilter) -> None:
        """|coro|

        Adds the given filters to the player's :class:`.FilterSink` and applies them immediately.

        This is the equivalent of calling :meth:`Player.filters.add() <.FilterSink.add>`
        and then :meth:`.Player.apply_filters` immediately.

        .. note::
            If you're applying multiple operations simultaneously to the filter sink,
            consider modifying the sink directly and then running :meth:`.Player.apply_filters`
            to apply them all at once.

        Parameters
        ----------
        *filters: :class:`.BaseFilter`
            The filters to add. Must inherit from :class:`.BaseFilter`.
        """
        self.filters.add(*filters)
        await self.apply_filters()

    async def remove_filters(self, *filters: Type[BaseFilter]) -> None:
        """|coro|

        Removes the given filters from the player's :class:`.FilterSink` and applies changes immediately.

        All values passed must be class objects (that is - the classes themselves) that subclass :class:`.BaseFilter`.
        For example, if you wanted to remove the equalizer filter, you would pass in ``Equalizer`` itself - not the instance.

        All given filters that are not in the player's filter sink will pass silently.

        This is the equivalent of calling :meth:`Player.filters.remove() <.FilterSink.remove>`
        and then :meth:`.Player.apply_filters` immediately.

        .. note::
            If you're applying multiple operations simultaneously to the filter sink,
            consider modifying the sink directly and then running :meth:`.Player.apply_filters`
            to apply them all at once.

        Parameters
        ----------
        *filters: Type[:class:`.BaseFilter`]
            The classes filters to remove. Each must subclass :class:`.BaseFilter`.
        """
        self.filters.remove(*filters)
        await self.apply_filters()

    async def overwrite_filters(self, *filters: BaseFilter) -> None:
        """|coro|

        Clears all filters in the player's :class:`.FilterSink`, overwrites them with the given filters,
        and applies them immediately.

        This is the equivalent of calling :meth:`Player.filters.overwrite() <.FilterSink.overwrite>`
        and then :meth:`.Player.apply_filters` immediately.

        .. note::
            If you're applying multiple operations simultaneously to the filter sink,
            consider modifying the sink directly and then running :meth:`.Player.apply_filters`
            to apply them all at once.

        Parameters
        ----------
        *filters: :class:`.BaseFilter`
            The filters to overwrite. Must inherit from :class:`.BaseFilter`.
        """
        self.filters.overwrite(*filters)
        await self.apply_filters()

    async def clear_filters(self) -> None:
        """|coro|

        Clears all filters from the player's :class:`.FilterSink` and applies changes immediately.

        This is the equivalent of calling :meth:`Player.filters.clear() <.FilterSink.clear>`
        and then :meth:`.Player.apply_filters` immediately.

        .. note::
            If you're applying multiple operations simultaneously to the filter sink,
            consider modifying the sink directly and then running :meth:`.Player.apply_filters`
            to apply them all at once.
        """
        self.filters.clear()
        await self.apply_filters()

    def event(self, coro: Callable[[BaseEvent], Awaitable[Any]], /) -> Callable[[BaseEvent], Awaitable[Any]]:
        """A decorator that registers a coroutine function as an event handler for the given event.

        Parameters
        ----------
        coro: async (event: :class:`.BaseEvent`) -> Any
            The coroutine function to register.
        """
        setattr(self, coro.__name__, coro)
        log.debug('Registered event %r', coro.__name__)

        return coro

    def __repr__(self) -> str:
        return f'<Player node={self.node.identifier!r} guild_id={self.guild_id} channel_id={self.channel_id}>'
