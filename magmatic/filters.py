from __future__ import annotations

from abc import ABC
from typing import (
    Callable,
    ClassVar,
    Dict,
    Generic,
    Iterator,
    List,
    Literal,
    Optional,
    Tuple,
    TYPE_CHECKING,
    Type,
    TypeVar,
    Union,
    cast,
)

if TYPE_CHECKING:
    Number = Union[int, float]
    NumberDict = Dict[str, Number]
    NumberDictList = List[NumberDict]
    FilterPayload = Union[Number, NumberDict, NumberDictList]

    EqualizerBandIndex = Literal[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]
    TimescalePitch = Union[float, 'PitchMultiplier', 'PitchOctaves', 'PitchSemitones']

    FilterT = TypeVar('FilterT', bound='BaseFilter')
    SetterT = TypeVar('SetterT')
    NewSetterT = TypeVar('NewSetterT')

    class FilterProperty(property, Generic[FilterT, SetterT]):
        def __get__(self, instance: FilterSink, owner: Optional[Type[FilterSink]] = None) -> Optional[FilterT]:
            return cast(FilterT, super().__get__(instance, owner))

        def __set__(self, instance: FilterSink, value: SetterT) -> None:
            super().__set__(instance, value)

        def __delete__(self, instance: FilterSink) -> None:
            super().__delete__(instance)

__all__ = (
    'FilterSink',
    'BaseFilter',  # chose to export this for type-checking purposes
    'VolumeFilter',
    'Equalizer',
    'TimescaleFilter',
    'PitchMultiplier',
    'PitchOctaves',
    'PitchSemitones',
)


class BaseFilter(ABC):
    """The base class for which all filters must inherit from."""

    __slots__ = ()

    key: ClassVar[str]
    _repr_attrs: ClassVar[Tuple[str, ...]] = ()

    def to_dict(self) -> FilterPayload:
        """Returns a JSON-serializable payload for the filter. This is used to send the filter to Lavalink.

        Returns
        -------
        Any
            The JSON-serializable payload for the filter.
        """
        raise NotImplementedError

    def __walk_repr_attributes(self) -> Iterator[Tuple[str, str]]:
        for attr in self._repr_attrs:
            try:
                value = getattr(self, attr)
            except AttributeError:
                continue

            if value := repr(value):
                yield attr, value

    def __repr__(self) -> str:
        attrs = ' '.join(f'{attr}={value}' for attr, value in self.__walk_repr_attributes())
        return f'<{self.__class__.__name__}{attrs and " " + attrs}>'


class VolumeFilter(BaseFilter):
    """A filter that modifies the player's volume.

    .. note::
        This should not be used with :meth:`.Player.set_volume` as the two
        will overwrite each other; they will not stack.

        Additionally, :attr:`.Player.volume` will return the volume on the player,
        not the volume on this filter.

    Parameters
    ----------
    volume: :class:`float`
        The volume as a float between 0 and 5. If the volume is a percentage, divide by 100 first.

        ``1.0`` is the default volume (100%).
    """

    __slots__ = ('_volume',)

    key = 'volume'
    _repr_attrs = ('volume',)

    if TYPE_CHECKING:
        _volume: float

    def __init__(self, volume: float = 1.0) -> None:
        self.volume = volume

    @property
    def volume(self) -> float:
        """:class:`float`: The volume as a float between 0 and 5.

        To retrieve the volume as a percentage, multiply this value by 100.
        """
        return self._volume

    @volume.setter
    def volume(self, volume: float) -> None:
        if not isinstance(volume, float):
            raise TypeError(f'volume must be a float, not {type(volume)!r}')

        if not 0 <= volume <= 5:
            raise ValueError('volume must be between 0 and 5')

        self._volume = volume

    def to_dict(self) -> Number:
        return self._volume

    def __float__(self) -> float:
        return self._volume


class Equalizer(BaseFilter):
    """A filter that modifies the equalizer bands of the player.

    Attributes
    ----------
    name: Optional[:class:`str`]
        The identifying name for this equalizer. Useful for displaying
        which equalizer the user is using.

        If no name is set, this will be ``None``.

    Parameters
    ----------
    *gains: float
        The band gains for this equalizer. There are a total of 15 bands.
        Each gain must be between -0.25 and +1.0.

        Either leave this blank or specify exactly 15 bands.
    name: Optional[:class:`str`]
        The identifying name for the equalizer. Useful for displaying
        which equalizer the user is using. Defaults to ``None``.

    Raises
    ------
    ValueError
        You did not specify exactly 0 or 15 bands
    """

    __slots__ = ('_gains', 'name')

    key = 'equalizer'
    _repr_attrs = ('name',)

    if TYPE_CHECKING:
        _gains: List[float]
        name: Optional[str]

    def __init__(self, *gains: float, name: Optional[str] = None) -> None:
        self.name: Optional[str] = name

        if not gains:
            self.reset()
        else:
            self.set_bands(*gains)

    @property
    def bands(self) -> List[float]:
        """list[:class:`float`]: A list of the gains for all 15 bands in this equalizer.

        There will always be 15 items in the returned list.

        You can retrieve an index-to-gain mapping by using a builtin function such as :py:function:`enumerate`.
        """
        return self._gains

    def get_band(self, index: EqualizerBandIndex) -> float:
        """Retrieve the gain for a specific band at a specifix index.

        Parameters
        ----------
        index: :class:`int`
            The index of the band to retrieve. Must be between 0 and 14.

        Returns
        -------
        :class:`float`
            The gain for the specified band.

        Raises
        ------
        IndexError
            The index is out of range. (Not between 0 and 14)
        """
        return self._gains[index]

    def set_band_at(self, index: EqualizerBandIndex, /, gain: float) -> None:
        """Sets the gain for a specific band at a specifix index to the given gain.

        Parameters
        ----------
        index: :class:`int`
            The index of the band the set. Must be between 0 and 14.

        Raises
        ------
        IndexError
            The index is out of range.
        """
        self._gains[index] = gain

    def set_bands(self, *gains: float) -> None:
        """Overwrites the band gains for this equalizer. Exactly 15 gains must be specified.

        Furthermore, each gain must be between -0.25 and +1.0.

        Parameters
        ----------
        *gains: :class:`float`
            The new gains for the equalizer in order.

        Raises
        ------
        ValueError
            You did not specify exactly 15 bands
        """
        if len(gains) != 15:
            raise ValueError(f'must specify exactly 15 bands, got {len(gains)} instead')

        if any(not -0.25 <= gain <= 1.0 for gain in gains):
            raise ValueError('each gain must be between -0.25 and +1.0')

        self._gains = list(gains)

    def reset(self) -> None:
        """Resets the equalizer band gains to the default values."""
        self._gains = [0] * 15

    def to_dict(self) -> NumberDictList:
        return [
            {'band': i, 'gain': gain}
            for i, gain in enumerate(self._gains)
        ]

    @classmethod
    def flat(cls) -> Equalizer:
        """Returns a flat equalizer with all bands set to 0.0."""
        return cls(name='flat')

    @classmethod
    def boost(cls) -> Equalizer:
        """Returns an equalizer which puts an emphasis on punchy-bass and mid-high tones."""
        return cls(
            -0.075, 0.125, 0.125, 0.1, 0.1, 0.05, 0.075, 0, 0, 0, 0, 0, 0.125, 0.15, 0.05,
            name='boost',
        )

    @classmethod
    def metal(cls) -> Equalizer:
        """Returns an equalizer suitable for metal/rock music."""
        return cls(
            0, 0.1, 0.1, 0.15, 0.13, 0.1, 0, 0.125, 0.175, 0.175, 0.125, 0.125, 0.1, 0.075, 0,
            name='metal',
        )

    @classmethod
    def piano(cls) -> Equalizer:
        """Returns an equalizer suitable for piano music or music with high tones.

        This may cut off some bass tones.
        """
        return cls(
            -0.25, -0.25, -0.125, 0, 0.25, 0.25, 0, -0.25, -0.25, 0, 0, 0.5, 0.25, -0.025, 0,
            name='piano',
        )

    @classmethod
    def jazz(cls) -> Equalizer:
        """Returns an equalizer suitable for jazzy music."""
        return cls(
            -0.13, -0.11, 0.1, -0.1, 0.14, 0.2, -0.18, 0, 0.24, 0.22, 0.2, 0, 0, 0, 0,
            name='jazz',
        )

    @classmethod
    def pop(cls) -> Equalizer:
        """Returns an equalizer suitable for pop music."""
        return cls(
            -0.02, -0.01, 0.08, 0.1, 0.15, 0.1, 0.03, -0.02, -0.035, -0.05, -0.05, -0.05, -0.05, -0.05, -0.05,
            name='pop',
        )

    def __getitem__(self, index: EqualizerBandIndex) -> float:
        return self.get_band(index)

    def __setitem__(self, index: EqualizerBandIndex, value: float) -> None:
        self.set_band_at(index, gain=value)

    def __iter__(self):
        return iter(self._gains)


class _TimescalePitchValue(ABC):
    def __init__(self, value: float, /) -> None:
        self._value: float = value

    def __float__(self) -> float:
        raise NotImplementedError


class PitchMultiplier(_TimescalePitchValue):
    def __float__(self) -> float:
        return self._value


class PitchOctaves(_TimescalePitchValue):
    def __float__(self) -> float:
        return 2 ** self._value


class PitchSemitones(_TimescalePitchValue):
    def __float__(self) -> float:
        return 2 ** (self._value / 12)


class TimescaleFilter(BaseFilter):
    """A filter which modifies the piatch, speed, and rate of the audio.

    All parameters are optional and default to ``1.0``.

    Parameters
    ----------
    speed: :class:`float`
        The speed multiplier. For example, a value of ``2`` will double the speed of the audio.
    pitch: Union[:class:`float`, `magmatic.filters.PitchMultiplier`, `magmatic.filters.PitchOctaves`, `magmatic.filters.PitchSemitones`]
        The pitch multiplier/relative value. A higher value makes the audio a higher pitch.

        Passing in a raw float will default to it being a normal multiplier.
        You can pass in special values such as ``magmatic.filters.PitchOctaves(1)`` to use octaves instead, for example.

        The following are available:

        +--------------------------------------+----------------------------------------------------------------------+
        | ``magmatic.filters.PitchMultiplier`` | Modifies the multiplier of the pitch relative to the original pitch. |
        |                                      | A value of ``1.0`` will not change the pitch.                        |
        +--------------------------------------+----------------------------------------------------------------------+
        | ``magmatic.filters.PitchOctaves``    | Modifies the amount of octaves the pitch should change by relative   |
        |                                      | to the original pitch. A value of ``0.0`` will not change the pitch. |
        +--------------------------------------+----------------------------------------------------------------------+
        | ``magmatic.filters.PitchSemitones``  | Modifies the amount of semitones the pitch should change by relative |
        |                                      | to the original pitch. A value of ``0.0`` will not change the pitch. |
        |                                      | 12 semitones make up an octave.                                      |
        +--------------------------------------+----------------------------------------------------------------------+
    rate: :class:`float`
        The rate multiplier.
    """

    __slots__ = ('_speed', '_pitch', '_rate')

    key = 'timescale'
    _repr_attrs = ('speed', 'pitch', 'rate')

    if TYPE_CHECKING:
        _speed: float
        _pitch: float
        _rate: float

    def __init__(self, *, speed: float = 1.0, pitch: TimescalePitch = 1.0, rate: float = 1.0) -> None:
        self.update(speed=speed, pitch=pitch, rate=rate)

    @property
    def speed(self) -> float:
        """:class:`float`: The speed multiplier represented as a float. A value of ``1.0`` is the original speed."""
        return self._speed

    @speed.setter
    def speed(self, value: float) -> None:
        if value < 0:
            raise ValueError('speed multiplier cannot be negative')

        self._speed = value

    @property
    def pitch(self) -> float:
        """:class:`float`: The pitch multiplier represented as a float. A value of ``1.0`` is the original pitch."""
        return self._pitch

    @pitch.setter
    def pitch(self, value: TimescalePitch) -> None:
        value = float(value)

        if value < 0:
            raise ValueError('pitch multiplier cannot be negative')

        self._pitch = value

    @property
    def rate(self) -> float:
        """:class:`float`: The rate multiplier represented as a float. A value of ``1.0`` is the original rate."""
        return self._rate

    @rate.setter
    def rate(self, value: float) -> None:
        if value < 0:
            raise ValueError('rate multiplier cannot be negative')

        self._rate = value

    def update(
        self,
        *,
        speed: Optional[float] = None,
        pitch: Optional[TimescalePitch] = None,
        rate: Optional[float] = None,
    ) -> None:
        """Modifies the speed, pitch, and rate multipliers with the given values.

        All parameters are optional and keyword-only.

        Parameters
        ----------
        speed: :class:`float`
            The new speed multiplier.
        pitch: Union[:class:`float`, `magmatic.filters.PitchMultiplier`, `magmatic.filters.PitchOctaves`, `magmatic.filters.PitchSemitones`]
            The new pitch multiplier/relative value. See documentation on :class:`.TimescaleFilter` for more information.
        rate: :class:`float`
            The new rate multiplier.
        """
        if speed is not None:
            self.speed = speed

        if pitch is not None:
            # noinspection PyTypeChecker
            self.pitch = pitch

        if rate is not None:
            self.rate = rate

    def to_dict(self) -> NumberDict:
        return {
            'speed': self.speed,
            'pitch': self.pitch,
            'rate': self.rate,
        }


def filter_property(key: str, cls: Type[FilterT]) -> Callable[
    [Callable[..., Optional[FilterT]]], FilterProperty[FilterT, FilterT]
]:
    def decorator(func: Callable[..., Optional[FilterT]]) -> FilterProperty[FilterT, FilterT]:
        def getter(self: FilterSink) -> Optional[FilterT]:
            resolved = self._filters.get(key)
            assert isinstance(resolved, cls)
            return resolved

        getter.__filter_property__ = True

        def setter(self: FilterSink, value: FilterT) -> None:
            if not isinstance(value, cls):
                raise TypeError(f'expected {cls.__name__}, got {type(value)}')

            self._filters[key] = value

        def deleter(self: FilterSink) -> None:
            del self._filters[key]

        return cast(
            'FilterProperty[FilterT, FilterT]', property(getter, setter, deleter, func.__doc__),
        )

    return decorator


class FilterSink:
    """Represents a sink of filters. All filters in the sink must inherit from :class:`.BaseFilter`.

    These are unique for each :class:`.Player` instance.

    Usage ::

        player = ...  # retrieve your Player instance
        sink = player.filters
        sink.add(
            magmatic.VolumeFilter(volume=0.5),
            magmatic.Equalizer.pop(),
        )
        del sink.equalizer  # Removes the equalizer filter using del
        sink.remove(magmatic.Equalizer)  # Removes the equalizer filter using FilterSink.remove
        sink.clear()  # Removes all filters

        # Once we're all done...
        await player.update_filters()
    """

    __slots__ = ('_filters',)

    _default: ClassVar[Dict[str, BaseFilter]] = {
        'volume': VolumeFilter(),
        'equalizer': Equalizer(),
        'timescale': TimescaleFilter(),
    }

    def __init__(self) -> None:
        self._filters: Dict[str, BaseFilter] = {}

    # volume is a special case
    @property
    def volume(self) -> Optional[VolumeFilter]:
        """The volume filter of this sink.

        You can cast this to a :py:class:`float` to retrieve the actual volume number.

        Returns
        -------
        Optional[:class:`.VolumeFilter`]
            The volume filter instance. ``None`` if there is no volume filter.
        """
        return cast(Optional[VolumeFilter], ...) if TYPE_CHECKING else self._filters.get('volume')

    @volume.setter
    def volume(self, value: Union[VolumeFilter, float]) -> None:
        if isinstance(value, float):
            value = VolumeFilter(value)
        elif not isinstance(value, VolumeFilter):
            raise TypeError(f'expected VolumeFilter or float, got {type(value)}')

        self._filters['volume'] = value

    @volume.deleter
    def volume(self) -> None:
        del self._filters['volume']

    volume.fget.__filter_property__ = True

    @filter_property('equalizer', Equalizer)
    def equalizer(self) -> Optional[Equalizer]:
        """The equalizer instance associated with this sink.

        Returns
        -------
        Optional[:class:`.Equalizer`]
            The equalizer instance. ``None`` if there is no equalizer.
        """

    @filter_property('timescale', TimescaleFilter)
    def timescale(self) -> Optional[TimescaleFilter]:
        """The timescale filter of this sink.

        Returns
        -------
        Optional[:class:`.TimescaleFilter`]
            The timescale filter instance. ``None`` if there is no timescale filter.
        """

    def add(self, *filters: BaseFilter) -> None:
        """Adds a filter (or multiple) to the sink.

        All values passed must be instances of classes that inherit from :class:`.BaseFilter`.

        Filter keys are determined by their class. Supplying multiple filters
        of the same class will overwrite the previous values.

        Parameters
        ----------
        *filters: :class:`.BaseFilter`
            The filters to add to the sink.

        Raises
        ------
        TypeError
            The values passed are not instances of :class:`.BaseFilter`.
        """
        for value in filters:
            if not isinstance(value, BaseFilter):
                raise TypeError(f'{value!r} is not an instance of BaseFilter')

            self._filters[value.__class__.key] = value

    def remove(self, *filters: Type[BaseFilter]) -> None:
        """Removes a filter (or multiple) from the sink.

        All values passed must be class objects (that is - the classes themselves) that subclass :class:`.BaseFilter`.
        For example, if you wanted to remove the equalizer filter, you would pass in ``Equalizer`` itself - not the instance.

        All given filters that are not in the sink will pass silently.

        Parameters
        ----------
        *filters: Type[:class:`BaseFilter`]
            The classes of the filters to remove from the sink.

        Raises
        ------
        TypeError
            The values passed are not classes that subclass :class:`.BaseFilter`.
        """
        for value in filters:
            if not isinstance(value, type):
                raise TypeError(f'{value!r} is not a class')

            if not issubclass(value, BaseFilter):
                raise TypeError(f'{value!r} is not a subclass of BaseFilter')

            try:
                del self._filters[value.key]
            except KeyError:
                pass

    def overwrite(self, *filters: BaseFilter) -> None:
        """Overwrites the sink's filters with the given filters.

        This is the equivalent of running :meth:`.FilterSink.clear` followed by :meth:`.FilterSink.add` with
        your filters.

        Parameters
        ----------
        *filters: :class:`.BaseFilter`
            The filters to overwrite the sink with.

        Raises
        ------
        TypeError
            The values passed are not instances of :class:`.BaseFilter`.
        """
        self.clear()
        self.add(*filters)

    def clear(self) -> None:
        """Clears all filters from the sink."""
        self._filters.clear()

    def to_dict(self) -> Dict[str, FilterPayload]:
        """Returns a JSON-serializable payload made of all filters in the sink.

        This is used to send the filters to Lavalink.

        Returns
        -------
        dict[:class:`str`, Any]
            The JSON-serializable payload for the filters.
        """
        result = {
            key: value.to_dict()
            for key, value in self._filters.items()
        }
        return {
            **{k: v.to_dict() for k, v in self._default.items()},
            **result,
        }

    def __repr__(self) -> str:
        if not self._filters:
            return '<FilterSink>'

        info = ' '.join(f'{k}={v!r}' for k, v in self._filters.items())
        return f'<FilterSink {info}>'

    def __iter__(self) -> Iterator[BaseFilter]:
        return iter(self._filters.values())
