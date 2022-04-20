.. currentmodule:: magmatic

Magmatic API Reference
======================


Magmatic provides a simple yet powerful interface around Lavalink.

Nodes
-----

NodePool
~~~~~~~~

.. autoclass:: NodePool
    :members:

Top-level DefaultNodePool functions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

create_node
+++++++++++

.. autofunction:: create_node

start_node
++++++++++

.. autofunction:: start_node

add_node
++++++++

.. autofunction:: add_node

get_node
++++++++

.. autofunction:: get_node

get_player
++++++++++

.. autofunction:: get_player

Node
~~~~

.. autoclass:: Node()
    :members:

.. autoclass:: node.ConnectionManager()

Players
-------

Player
~~~~~~

.. autoclass:: Player(*, node, guild)
    :members:

Tracks
------

Track
~~~~~

.. autoclass:: Track()
    :members:

Playlist
~~~~~~~~

.. autoclass:: Playlist()
    :members:

Track Converters
~~~~~~~~~~~~~~~~

.. autoclass:: YoutubeTrack()
    :members:

.. autoclass:: YoutubeMusicTrack()
    :members:

.. autoclass:: SoundCloudTrack()
    :members:

.. autoclass:: SpotifyTrack()
    :members:

Filters
-------

FilterSink
~~~~~~~~~~

.. autoclass:: FilterSink
    :members:

BaseFilter
~~~~~~~~~~

.. autoclass:: BaseFilter
    :members:

VolumeFilter
~~~~~~~~~~~~

.. autoclass:: VolumeFilter
    :members:
    :inherited-members:

Equalizer
~~~~~~~~~

.. autoclass:: Equalizer
    :members:
    :inherited-members:

TimescaleFilter
~~~~~~~~~~~~~~~

.. autoclass:: TimescaleFilter
    :members:
    :inherited-members:

Event Models
------------

See :ref:`Event Reference` for more information on events.

TrackStartEvent
~~~~~~~~~~~~~~~

.. autoclass:: TrackStartEvent()
    :members:
    :inherited-members:

TrackEndEvent
~~~~~~~~~~~~~~

.. autoclass:: TrackEndEvent()
    :members:
    :inherited-members:

TrackExceptionEvent
~~~~~~~~~~~~~~~~~~~

.. autoclass:: TrackExceptionEvent()
    :members:
    :inherited-members:

TrackStuckEvent
~~~~~~~~~~~~~~~

.. autoclass:: TrackStuckEvent()
    :members:
    :inherited-members:

WebSocketCloseEvent
~~~~~~~~~~~~~~~~~~~

.. autoclass:: WebSocketCloseEvent()
    :members:
    :inherited-members:

Event Reference
---------------

This section goes over all events dispatched by magmatic.
You can handle most of these events in two different ways:

Through your discord.py client/bot instance: ::

    class MyMusicBot(commands.Bot):
        async def on_magmatic_node_ready(self, node):
            print(f'Node {node.identifier} is ready!')

        async def on_magmatic_track_start(self, player, event):
            track = await event.track()
            print(f'Player in {player.guild.name} started playing {track.title!r}')

    # or...
    @bot.event
    async def on_magmatic_node_ready(node):
        print(f'Node {node.identifier} is ready!')

Or, for all non-node related events (that is, events that do not contain "node" in their name),
they can be handled through a :class:`Player` subclass: ::

    class MyCustomPlayer(magmatic.Player):
        # Notice the absence of "on_magmatic_" and instead just "on_"
        async def on_track_start(self, event):
            track = await event.track()
            print(f'Player in {self.guild.name} started playing {track.title!r}')

For events that can be implemented in both ways, the top event is documented as
the signature for a discord.py client/bot listener while the second if documented
as the signature for a :class:`Player`.

Node-related Events
~~~~~~~~~~~~~~~~~~~

.. function:: on_magmatic_node_ready(node)

    Called when a :class:`Node` successfully connects with Lavalink.

    :param node: The node that is ready.
    :type node: :class:`Node`

Track-related Events
~~~~~~~~~~~~~~~~~~~~

.. function:: on_magmatic_track_start(player, event)
              Player.on_track_start(event)

    Called when a :class:`Player` starts playing a :class:`Track`.

    :param player: The player that started playing a track.
    :type player: :class:`Player`
    :param event: The event object.
    :type event: :class:`TrackStartEvent`

.. function:: on_magmatic_track_end(player, event)
              Player.on_track_end(event)

    Called when a track stops playing.

    :param player: The player that finished playing a track.
    :type player: :class:`Player`
    :param event: The event object.
    :type event: :class:`TrackEndEvent`

.. function:: on_magmatic_track_exception(player, event)
              Player.on_track_exception(event)

    Called when a track encounters an error while playing.

    :param player: The player that encountered an error.
    :type player: :class:`Player`
    :param event: The event object.
    :type event: :class:`TrackExceptionEvent`

.. function:: on_magmatic_track_stuck(player, event)
              Player.on_track_stuck(event)

    Called when a track is stuck.

    :param player: The player that encountered a stuck track.
    :type player: :class:`Player`
    :param event: The event object.
    :type event: :class:`TrackStuckEvent`

Websocket-related Events
~~~~~~~~~~~~~~~~~~~~~~~~

.. function:: on_magmatic_websocket_close(player, event)
              Player.on_websocket_close(event)

    Called when a Discord websocket connection is closed on a player.

    .. note::
        This is not the event for when a :class:`Node` closes.

    :param player: The player that encountered a websocket close.
    :type player: :class:`Player`
    :param event: The event object.
    :type event: :class:`WebSocketCloseEvent`

Stats
-----

Stats
~~~~~

.. autoclass:: Stats()
    :members:

MemoryStats
~~~~~~~~~~~

.. autoclass:: MemoryStats()
    :members:

Enums
-----

Source
~~~~~~

.. autoenum:: Source()
    :members:

LoadSource
~~~~~~~~~~

.. autoenum:: LoadSource()
    :members:

LoadType
~~~~~~~~

.. autoenum:: LoadType()
    :members:

ErrorSeverity
~~~~~~~~~~~~~

.. autoenum:: ErrorSeverity()
    :members:

TrackEndReason
~~~~~~~~~~~~~~

.. autoenum:: TrackEndReason()
    :members:

Internal Enums
~~~~~~~~~~~~~~

.. autoenum:: OpCode()
    :members:

.. autoenum:: EventType()
    :members:
