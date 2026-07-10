"""Shared constants and geometry helpers of the vertical-farm water
checks (transient-pulse hydraulics bands, wet-region and drainage math)."""
from __future__ import annotations

from artifact_forge_ng.product.archetype import RegionRole
from artifact_forge_ng.form.part import PartForm
from artifact_forge_ng.form.regions import Box3

#: The transient-pulse hydraulics bands (docs/VERTICAL_FARM_PACK.md).
#: MOUNT_SLOPE_BAND is the operational band the mounted row must sit at —
#: the rail itself is level (constant depth); the mount supplies the fall.
MOUNT_SLOPE_BAND = (1.0, 2.0)  # degrees, mount_context
CONST_DEPTH_TOL = 0.05  # channel floor level end to end
CHANNEL_D_BAND = (4.0, 8.0)
CHANNEL_W_BAND = (12.0, 20.0)
BOTTOM_R_BAND = (0.8, 2.0)
FLOOR_MARGIN_MIN = 2.0  # material below the deepest floor point
SEAT_CLEARANCE_BAND = (0.5, 1.0)
TG_SIDE_CLEARANCE_BAND = (0.3, 0.5)  # tongue/groove per-side
TG_BOTTOM_MARGIN = 0.3  # tongue never bottoms in the groove
# -- lap-flow handover bands (VF correction) ----------------------------------
LAP_LIP_LEN_BAND = (3.0, 6.0)  # lip protrusion past the face
LAP_LIP_T_BAND = (1.2, 1.6)
LAP_SIDE_CLEAR_BAND = (0.3, 0.5)  # lip in the receiver, per side
LAP_SLOT_BAND = (0.5, 2.5)  # deliberate open slot at the lip tip
FACE_GAP_BAND = (0.3, 0.6)  # controlled flush face gap
LAP_LATERAL_CLEAR_MIN = 40.0  # slot drips stay this far from dry hardware
MAGNET_WET_WALL_MIN = 1.2  # plastic between a magnet pocket and any water
MAGNET_FIT_BAND = (0.1, 0.3)  # diametral press-fit — pushes in, stays put
LW_RIB_MIN = 1.8
CASSETTE_COVER = 4.0  # every skeleton opening hides this far under the seat
CASSETTE_SPAN_MAX = 45.0  # worst unsupported span under the cassette floor

def _boxes_overlap(a: Box3, b: Box3) -> bool:
    return (
        a.x0 <= b.x1 and b.x0 <= a.x1
        and a.y0 <= b.y1 and b.y0 <= a.y1
        and a.z0 <= b.z1 and b.z0 <= a.z1
    )


def _wet_regions(form: PartForm):
    return [r for r in form.regions if r.role is RegionRole.TRANSIENT_WATER_PATH]


def _blind_bore_drained_below(bore, bores) -> bool:
    """VF-9.2: a vertical bore blind at the BOTTOM does not pool when a
    coaxial bore adjoins its blind floor and continues downward — the stepped
    tube socket draining through its drip orifice. The stop shoulder is the
    intended tube seat, not a hidden sump."""
    if bore.axis != "Z" or bore.overshoot[0] > 0.0:
        return False  # only a bottom-blind Z bore qualifies
    bottom = min(bore.span)
    for other in bores:
        if other is bore or other.axis != "Z":
            continue
        if (abs(other.center[0] - bore.center[0]) <= 0.1
                and abs(other.center[1] - bore.center[1]) <= 0.1
                and max(other.span) >= bottom - 0.1
                and min(other.span) < bottom - 0.1):
            return True
    return False


def _pocket_drained_by_through_bore(box, bores) -> bool:
    """A floored pocket does NOT pool if a vertical open-bottom bore passes
    through its footprint down to (or below) the pocket floor: the floor has
    a drain hole in it, so water leaves through the underside. This is the
    strainer-seat recess sitting directly over the collector's vertical drain
    (VF-8) — the recess floor carries the drain bore straight to the bottom."""
    for bore in bores:
        if bore.axis != "Z" or bore.overshoot[0] <= 0.0:
            continue  # only a downward-open (through-to-underside) Z bore drains
        if bore.span[0] > box.z0 + 0.05:
            continue  # the bore does not reach down to the pocket floor
        bx, by = bore.center[0], bore.center[1]
        if (box.x0 - 0.05 <= bx <= box.x1 + 0.05
                and box.y0 - 0.05 <= by <= box.y1 + 0.05):
            return True
    return False


