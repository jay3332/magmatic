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

.. autofunction:: create_node

.. autofunction:: start_node

.. autofunction:: add_node

.. autofunction:: get_node

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

.. autoclass:: Player
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

Stats
-----

Stats
~~~~~

.. autoclass:: Stats
    :members:

MemoryStats
~~~~~~~~~~~

.. autoclass:: MemoryStats
    :members:

Enums
-----

.. autoclass:: OpCode
    :members:

.. autoclass:: EventType
    :members:
