"""A small, self-contained unit & dimension registry.

The platform spans wildly different domains -- structural brackets, biomedical
wearables, wind-charging energy stations -- so a parameter's *physical
dimension* (length, pressure, power, energy, angle ...) has to be a first-class,
checkable property. This module gives every unit a dimension and a conversion to
a canonical base unit, with no external dependency.

Canonical base units are chosen to match the CAD kernel and common engineering
practice: length in mm, angle in deg (CadQuery convention), the rest broadly SI.

Conversion model (handles temperature offsets cleanly):

    base_value = value * unit.factor + unit.offset
    value      = (base_value - unit.offset) / unit.factor
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import pi


class Dimension(Enum):
    DIMENSIONLESS = "dimensionless"
    LENGTH = "length"
    AREA = "area"
    VOLUME = "volume"
    ANGLE = "angle"
    MASS = "mass"
    TIME = "time"
    FREQUENCY = "frequency"
    VELOCITY = "velocity"
    FORCE = "force"
    PRESSURE = "pressure"
    VOLTAGE = "voltage"
    CURRENT = "current"
    POWER = "power"
    ENERGY = "energy"
    CHARGE = "charge"
    TEMPERATURE = "temperature"


@dataclass(frozen=True)
class Unit:
    symbol: str
    dimension: Dimension
    factor: float = 1.0
    offset: float = 0.0


def _build_registry() -> dict[str, Unit]:
    D = Dimension
    units: list[Unit] = [
        # dimensionless
        Unit("", D.DIMENSIONLESS, 1.0),
        Unit("%", D.DIMENSIONLESS, 0.01),
        Unit("count", D.DIMENSIONLESS, 1.0),
        # length (base: mm)
        Unit("mm", D.LENGTH, 1.0),
        Unit("um", D.LENGTH, 1e-3),
        Unit("cm", D.LENGTH, 10.0),
        Unit("m", D.LENGTH, 1000.0),
        Unit("in", D.LENGTH, 25.4),
        Unit("ft", D.LENGTH, 304.8),
        # area (base: mm^2)
        Unit("mm^2", D.AREA, 1.0),
        Unit("cm^2", D.AREA, 100.0),
        Unit("m^2", D.AREA, 1e6),
        # volume (base: mm^3)
        Unit("mm^3", D.VOLUME, 1.0),
        Unit("cm^3", D.VOLUME, 1000.0),
        Unit("mL", D.VOLUME, 1000.0),
        Unit("L", D.VOLUME, 1e6),
        # angle (base: deg)
        Unit("deg", D.ANGLE, 1.0),
        Unit("rad", D.ANGLE, 180.0 / pi),
        # mass (base: g)
        Unit("g", D.MASS, 1.0),
        Unit("mg", D.MASS, 1e-3),
        Unit("kg", D.MASS, 1000.0),
        # time (base: s)
        Unit("s", D.TIME, 1.0),
        Unit("ms", D.TIME, 1e-3),
        Unit("min", D.TIME, 60.0),
        Unit("h", D.TIME, 3600.0),
        # frequency (base: Hz)
        Unit("Hz", D.FREQUENCY, 1.0),
        Unit("kHz", D.FREQUENCY, 1000.0),
        Unit("rpm", D.FREQUENCY, 1.0 / 60.0),
        # velocity (base: m/s)
        Unit("m/s", D.VELOCITY, 1.0),
        Unit("km/h", D.VELOCITY, 1.0 / 3.6),
        # force (base: N)
        Unit("N", D.FORCE, 1.0),
        Unit("kN", D.FORCE, 1000.0),
        # pressure (base: Pa)
        Unit("Pa", D.PRESSURE, 1.0),
        Unit("kPa", D.PRESSURE, 1000.0),
        Unit("MPa", D.PRESSURE, 1e6),
        Unit("bar", D.PRESSURE, 1e5),
        Unit("psi", D.PRESSURE, 6894.757),
        Unit("mmHg", D.PRESSURE, 133.322),  # biomedical: blood pressure
        # voltage (base: V)
        Unit("V", D.VOLTAGE, 1.0),
        Unit("mV", D.VOLTAGE, 1e-3),
        Unit("kV", D.VOLTAGE, 1000.0),
        # current (base: A)
        Unit("A", D.CURRENT, 1.0),
        Unit("mA", D.CURRENT, 1e-3),
        # power (base: W)
        Unit("W", D.POWER, 1.0),
        Unit("mW", D.POWER, 1e-3),
        Unit("kW", D.POWER, 1000.0),
        # energy (base: J)
        Unit("J", D.ENERGY, 1.0),
        Unit("kJ", D.ENERGY, 1000.0),
        Unit("Wh", D.ENERGY, 3600.0),
        Unit("kWh", D.ENERGY, 3.6e6),
        Unit("mWh", D.ENERGY, 3.6),
        # charge (base: C); mAh is common for batteries
        Unit("C", D.CHARGE, 1.0),
        Unit("mAh", D.CHARGE, 3.6),
        Unit("Ah", D.CHARGE, 3600.0),
        # temperature (base: degC, with offsets)
        Unit("degC", D.TEMPERATURE, 1.0, 0.0),
        Unit("K", D.TEMPERATURE, 1.0, -273.15),
        Unit("degF", D.TEMPERATURE, 5.0 / 9.0, -160.0 / 9.0),
    ]
    return {u.symbol: u for u in units}


_REGISTRY: dict[str, Unit] = _build_registry()


def is_known_unit(symbol: str) -> bool:
    return symbol in _REGISTRY


def get_unit(symbol: str) -> Unit:
    try:
        return _REGISTRY[symbol]
    except KeyError:
        raise KeyError(
            f"unknown unit {symbol!r}; known units: {sorted(_REGISTRY)}"
        ) from None


def dimension_of(symbol: str) -> Dimension:
    return get_unit(symbol).dimension


def convert(value: float, from_symbol: str, to_symbol: str) -> float:
    """Convert ``value`` from one unit to another within the same dimension."""
    src = get_unit(from_symbol)
    dst = get_unit(to_symbol)
    if src.dimension is not dst.dimension:
        raise ValueError(
            f"cannot convert {from_symbol!r} ({src.dimension.value}) to "
            f"{to_symbol!r} ({dst.dimension.value}): different dimensions"
        )
    base = value * src.factor + src.offset
    return (base - dst.offset) / dst.factor
