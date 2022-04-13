from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict

__all__ = (
    'MemoryStats',
    'Stats',
)


class MemoryStats:
    """Memory information about a given node.

    Attributes
    ----------
    free: int
        The amount of free memory on the node, in bytes.
    used: int
        The amount of memory the node is actively using, in bytes.
    allocated: int
        The amount of memory the node has allocated, in bytes.
    reservable: int
        The amount of memory the node is able to allocate, in bytes.
    """

    __slots__ = ('free', 'used', 'allocated', 'reservable')

    def __init__(self, data: Dict[str, int]) -> None:
        self.free: int = data['free']
        self.used: int = data['used']
        self.allocated: int = data['allocated']
        self.reservable: int = data['reservable']

    @property
    def total(self) -> int:
        """:class:`int`: The total amount of memory on the node, in bytes."""
        return self.free + self.used + self.allocated + self.reservable

    def __repr__(self) -> str:
        free = self.free
        used = self.used
        allocated = self.allocated
        reservable = self.reservable

        return f'<MemoryStats {free=} {used=} {allocated=} {reservable=}>'


class Stats:
    """Statistical information about a given node.

    Attributes
    ----------
    uptime: int
        The amount of time the node has been running, in seconds.
    players: int
        The amount of players currently connected to the node.
    playing_players: int
        The amount of players currently connected and playing audio on the node.
    memory: :class:`.MemoryStats`
        The memory information about the node.
    cpu_cores: int
        The amount of CPU cores the node is able to use.
    system_load: float
        The amount of load from the system.
    lavalink_load: float
        The amount of load from Lavalink.
    frames_sent: int
        The amount of frames sent to the node.
    frames_nulled: int
        The amount of frames nulled by the node.
    frames_deficit: int
        The amount of frames deficit by the node.
    penalty: float
        The amount of load-balancing penalty on the node.
    """

    __slots__ = (
        'uptime',
        'players', 
        'playing_players', 
        'memory',
        'cpu_cores', 
        'system_load', 
        'lavalink_load', 
        'frames_sent',
        'frames_nulled',
        'frames_deficit',
        'penalty',
    )

    def __init__(self, data: Dict[str, Any]) -> None:
        self.uptime: int = data['uptime']

        self.players: int = data['players']
        self.playing_players: int = data['playingPlayers']
        self.memory: MemoryStats = MemoryStats(data['memory'])

        cpu = data['cpu']
        self.cpu_cores: int = cpu['cores']
        self.system_load: float = cpu['systemLoad']
        self.lavalink_load: float = cpu['lavalinkLoad']

        frame_stats = data.get('frameStats', defaultdict(lambda: -1))
        self.frames_sent: int = frame_stats['sent']
        self.frames_nulled: int = frame_stats['nulled']
        self.frames_deficit: int = frame_stats['deficit']
        self.penalty: float = self._calculate_penalty()

    def _calculate_penalty(self) -> float:
        cpu_penalty = 1.05 ** (100 * self.system_load) * 10 - 10
        frame_penalty = 0

        if self.frames_nulled != -1:
            frame_penalty += (
                1.03 ** (500 * (self.frames_nulled / 3000))
             ) * 600 - 600

        if self.frames_deficit != -1:
            frame_penalty += (
                1.03 ** (500 * (self.frames_deficit / 3000))
            ) * 600 - 600

        return self.playing_players + cpu_penalty + frame_penalty
        
    def __repr__(self) -> str:
        return f'<Stats players={self.players}>'
