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


def hole_cut_dims(screw: str, through: float, head_style: str = "cone") -> dict[str, float]:
    """The ONE source of fastener cutter dimensions (mm) — shared by the
    BRep hole cutter (cad/holes.py) and the implicit-skin SDF hard cuts
    (compiler/implicit), so the two paths cannot drift apart.

    Keys: ``bore_d`` (clearance bore diameter incl. FDM slack), ``head_r``
    (nominal head radius), ``seat_r`` (head recess radius incl. the 0.3 mm
    fit slack), plus per style: cone countersink ``cs_depth``/``cs_tip_r``
    or cylindrical counterbore ``cb_depth``.
    """
    spec = screw_spec(screw)
    head_r = spec["head"] / 2.0
    dims: dict[str, float] = {
        "bore_d": spec["clear"] + FDM_CLEARANCE,
        "head_r": head_r,
        "seat_r": head_r + 0.3,
    }
    if head_style == "cylinder":
        # Counterbore: flat-bottomed recess that swallows a socket-cap
        # head, never deeper than half the stock.
        dims["cb_depth"] = min(spec["head"] * 0.8, through * 0.5)
    else:
        # Conical countersink for a flat head.
        dims["cs_depth"] = min(2.0, through * 0.4)
        dims["cs_tip_r"] = 0.5
    return dims


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
