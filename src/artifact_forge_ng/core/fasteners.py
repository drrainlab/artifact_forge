"""Real fastener dimensions (mm) — ported from v1 ``fasteners.py``.

Pure data, needed at the Form-IR level (keepout sizing) as well as by the
CAD compiler (hole/countersink cutting), so it lives in core.
"""

from __future__ import annotations

#: Radial slack added to a bore so an FDM-printed hole actually fits.
FDM_CLEARANCE = 0.2

SCREWS: dict[str, dict[str, float]] = {
    "m2": {"clear": 2.4, "tap": 1.7, "heatset": 3.2, "head": 4.0,
           "nut_af": 4.0, "nut_h": 1.6},
    "m2.5": {"clear": 2.9, "tap": 2.1, "heatset": 3.6, "head": 5.0,
             "nut_af": 5.0, "nut_h": 2.0},
    "m3": {"clear": 3.4, "tap": 2.5, "heatset": 4.0, "head": 5.5,
           "nut_af": 5.5, "nut_h": 2.4},
    "m4": {"clear": 4.5, "tap": 3.3, "heatset": 5.6, "head": 7.0,
           "nut_af": 7.0, "nut_h": 3.2},
    "m5": {"clear": 5.5, "tap": 4.2, "heatset": 6.4, "head": 8.5,
           "nut_af": 8.0, "nut_h": 4.0},
}


def screw_spec(name: str) -> dict[str, float]:
    key = name.lower()
    if key not in SCREWS:
        raise KeyError(f"unknown screw size {name!r}; known: {sorted(SCREWS)}")
    return SCREWS[key]


#: Standard lamp-socket insert housings (nominal; any explicit inner_d in a
#: product instance overrides the preset).
SOCKET_INSERTS: dict[str, dict[str, float]] = {
    "e27": {"housing_d": 40.0, "depth": 32.0},
    "gu10": {"housing_d": 35.0, "depth": 28.0},
}


def socket_insert_spec(name: str) -> dict[str, float]:
    key = name.lower()
    if key not in SOCKET_INSERTS:
        raise KeyError(f"unknown socket insert {name!r}; known: {sorted(SOCKET_INSERTS)}")
    return SOCKET_INSERTS[key]
