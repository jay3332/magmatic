from __future__ import annotations

from magmatic import FilterSink, PitchOctaves, PitchSemitones, TimescaleFilter, VolumeFilter
from magmatic.filters import VibratoFilter


def test_filter_sink():
    sink = FilterSink()

    sink.add(VolumeFilter(volume=0.5))
    sink.add(TimescaleFilter(speed=2.0))

    assert sink.volume is not None
    assert sink.volume.volume == 0.5

    assert sink.timescale is not None
    assert sink.timescale.speed == 2.0

    payload = sink.to_dict()
    assert payload['volume'] == 0.5
    assert payload['timescale']['speed'] == 2.0  # type: ignore


def test_filter_sink_remove():
    sink = FilterSink()
    sink.add(
        VolumeFilter(volume=0.5),
        TimescaleFilter(speed=2.0),
        VibratoFilter(depth=1.0),
    )
    sink.remove(VolumeFilter)

    assert sink.volume is None

    payload = sink.to_dict()
    assert payload['volume'] == 1.0


def test_filter_sink_property():
    sink = FilterSink()
    sink.add(
        TimescaleFilter(speed=2.0),
        VibratoFilter(depth=1.0),
    )

    sink.volume = 2.0
    assert sink.volume is not None
    assert sink.volume.volume == 2.0  # type: ignore

    del sink.volume
    assert sink.volume is None

    # noinspection PyUnresolvedReferences, PyDunderSlots
    sink.timescale = TimescaleFilter(speed=3.0)
    assert sink.timescale is not None
    assert sink.timescale.speed == 3.0  # type: ignore


def test_timescale_pitch():
    with_octaves = TimescaleFilter(pitch=PitchOctaves(3))
    assert with_octaves.pitch == 8.0

    with_semitones = TimescaleFilter(pitch=PitchSemitones(36))
    assert with_semitones.pitch == 8.0
