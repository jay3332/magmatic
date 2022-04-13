from __future__ import annotations

from typing import Any, Dict

__all__ = (
    'Stats',
)


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
    memory_free: int
        The amount of free memory on the node, in bytes.
    memory_used: int
        The amount of memory the node is actively using, in bytes.
    memory_allocated: int
        The amount of memory the node has allocated, in bytes.
    memory_reservable: int
        The amount of memory the node can allocate, in bytes.
    cpu_cores: int
        The amount of CPU cores the node is able to use.
    system_load: float
        The amount of load from the system.
    lavalink_load: float
        The amount of load from Lavalink.
    penalty: float
        The amount of load-balancing penalty on the node.
    """
    __slots__ = (
        'uptime',
        'players', 
        'playing_players', 
        'memory_free', 
        'memory_used', 
        'memory_allocated', 
        'memory_reservable', 
        'cpu_cores', 
        'system_load', 
        'lavalink_load', 
        'frames_sent',
        'frames_nulled',
        'frames_deficit',
        'penalty'
    )

    def __init__(self, data: Dict[str, Any]) -> None:
        self.uptime: int = data['uptime']

        self.players: int = data['players']
        self.playing_players: int = data['playingPlayers']

        memory = data['memory']
        self.memory_free: int = memory['free']
        self.memory_used: int = memory['used']
        self.memory_allocated: int = memory['allocated']
        self.memory_reservable: int = memory['reservable']

        cpu = data['cpu']
        self.cpu_cores: int = cpu['cores']
        self.system_load: float = cpu['systemLoad']
        self.lavalink_load: float = cpu['lavalinkLoad']

        frame_stats = data.get('frameStats', {})
        self.frames_sent: int = frame_stats.get('sent', -1)
        self.frames_nulled: int = frame_stats.get('nulled', -1)
        self.frames_deficit: int = frame_stats.get('deficit', -1)
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
