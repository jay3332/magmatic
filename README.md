# Magmatic
---
### What is Magmatic?
An asynchronous wrapper around Lavalink for discord.py.

### What makes your library so much better than pre-existing competitors?
Magmatic offers a much easier to understand API to the end user and overall a better DX.
Code written with magmatic will tend to be much more readable and intuitive to understand and write.

One very key "selling" point (selling as in downloading) would be the robust and easy-to-use support of filters:
```py
from magmatic import PitchOctaves, TimescaleFilter, VolumeFilter

await player.add_filters(
    VolumeFilter(2.0),
    TimescaleFilter(speed=2.0, pitch=PitchOctaves(1)),  # PitchOctaves(1) means +1 octave relative to the base
)
await player.remove_filters(VolumeFilter)  # volume is now 1 but timescalefilter is kept the same
await player.clear_filters()  # no more filters at all

# This makes multiple requests, how about just make one?
player.filters.add(...)
player.filters.remove(...)
player.filters.overwrite(...)
player.filters.clear()
await player.apply_filters()
```

**In many competing libraries:**
- Filters are not implemented completely yet.
- The interface for filters are extremely flawed.
- Code quality for filters is not up to standard and contains a lot of boilerplate.
<br/>

WaveLink implements filters very loosely on the `feature/filters` branch but the interface has not been developed at all:
A new instance of `Filters` must be reconstructed every time to do simple operations for filters which is not really good to use.

Building on to this, WaveLink implements a single `NodePool` class object which contains methods to create nodes.
I would say this implementation is fine but not very intuitive and straightforward to use. Magmatic uses `NodePool` instances and
functions (non-methods) on magmatic that wrap around the `NodePool` are added to a `DefaultNodePool`.
