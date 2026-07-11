"""Thread recipe ops — MODELED metric threads for printed pairs:
`threaded_plug_body` (a grip disc + externally threaded stud) and
`thread_internal_clearance` (a bore + internal groove sized so the
printed pair actually mates). Print-fit compensation is explicit and
banded; the coarse-pitch table is the vocabulary — a printed M3 is a
fantasy, the table starts where FDM threads work.
Measurement contract: :mod:`artifact_forge_ng.form.checks_thread`."""
from __future__ import annotations

from typing import Any

from .part import BoreFeature, ThreadFeature
from .profiles_revolve import loop_from_points
from .recipe_ops_core import RecipeError, RecipeOpDecl, RecipeState, _register
from .regions import Box3, Region
from .section import Pt, SectionProfile
from ..product.archetype import RegionRole

#: Metric coarse pitches that print: below M8 the ridge is nozzle noise.
THREADS: dict[str, tuple[float, float]] = {
    "m8": (8.0, 1.25),
    "m10": (10.0, 1.5),
    "m12": (12.0, 1.75),
    "m16": (16.0, 2.0),
    "m20": (20.0, 2.5),
    "m24": (24.0, 3.0),
    "m30": (30.0, 3.5),
}

#: Per-side diametral print-fit compensation band.
THREAD_FIT_BAND = (0.1, 0.5)
THREAD_MIN_TURNS = 4.0


def _thread_spec(name: str) -> tuple[float, float]:
    key = name.lower()
    if key not in THREADS:
        raise RecipeError(
            f"unknown thread {name!r}; printable coarse table: "
            f"{sorted(THREADS)}")
    return THREADS[key]


def _threaded_plug_body(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """A tank/jar plug: a knurl-less grip disc on the bed with an
    externally threaded stud rising from it (threads print standing up
    — the only orientation worth printing them in). The external major
    is REDUCED by the fit compensation so the printed pair mates."""
    if state.section is not None:
        raise RecipeError("threaded_plug_body must be the (single) base op")
    major, pitch = _thread_spec(p["thread"])
    fit = p["fit_compensation"]
    lo, hi = THREAD_FIT_BAND
    if not lo <= fit <= hi:
        raise RecipeError(
            f"fit_compensation {fit:g} outside [{lo:g}, {hi:g}]")
    stud_l = p["stud_l"]
    turns = stud_l / pitch
    if turns < THREAD_MIN_TURNS:
        raise RecipeError(
            f"stud {stud_l:g} gives {turns:.1f} turns of {p['thread']} — "
            f"needs {THREAD_MIN_TURNS:g} to carry any load")
    grip_d, grip_h = p["grip_d"], p["grip_h"]
    major_eff = major - fit
    depth = 0.6 * pitch
    core_r = major_eff / 2.0 - depth
    if grip_d < major + 6.0:
        raise RecipeError(
            f"grip Ø{grip_d:g} barely out-reaches the {p['thread']} thread "
            "— nothing to turn by hand (needs major + 6)")
    ch = min(1.5, pitch)
    top = grip_h + stud_l

    pts = [
        Pt(0.0, 0.0), Pt(grip_d / 2.0, 0.0),
        Pt(grip_d / 2.0, grip_h),
        Pt(core_r, grip_h),
        Pt(core_r, top - ch), Pt(core_r - ch, top),
        Pt(0.0, top),
    ]
    state.section = SectionProfile(
        name="recipe_revolve", outer=loop_from_points(pts),
        plane="XZ", width_axis="Y")
    state.kind = "profile_revolve"
    state.width = grip_d

    name = op_id or "plug"
    state.threads.append(ThreadFeature(
        name=f"{name}_thread", at=(0.0, 0.0),
        z0=grip_h, length=stud_l - ch,
        major_d=major_eff, pitch=pitch, internal=False))
    state.regions.append(Region(
        f"{name}_grip", RegionRole.MOUNTING_SURFACE,
        Box3(-grip_d / 2.0, -grip_d / 2.0, 0.0,
             grip_d / 2.0, grip_d / 2.0, grip_h)))
    state.datums["thread_axis"] = {
        "at": [0.0, 0.0, top], "rotate": [0.0, 0.0, 0.0]}
    state.frame.update({
        f"{name}_thread_major": major_eff,
        f"{name}_thread_pitch": pitch,
        f"{name}_thread_turns": (stud_l - ch) / pitch,
        f"{name}_thread_fit": fit,
        f"{name}_thread_internal": 0.0,
    })


_register(RecipeOpDecl(
    name="threaded_plug_body",
    kind="base",
    params={
        "thread": ("choice", "m20"),
        "fit_compensation": ("length", 0.2),
        "stud_l": ("length", 12.0),
        "grip_d": ("length", 36.0),
        "grip_h": ("length", 8.0),
    },
    validators=(
        "form.thread_spec_ok",
        "topology.thread_present",
        "topology.single_connected_solid",
    ),
    apply=_threaded_plug_body,
    description="grip disc + externally threaded stud (printable coarse "
                "metric table, fit-compensated for printed pairs)",
))


def _thread_internal_clearance(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """An internally threaded port: a minor-diameter bore plus the
    helical groove, the major ENLARGED by the fit compensation so the
    compensated external stud screws in. Vertical axis only."""
    state.require_base("thread_internal_clearance")
    major, pitch = _thread_spec(p["thread"])
    fit = p["fit_compensation"]
    lo, hi = THREAD_FIT_BAND
    if not lo <= fit <= hi:
        raise RecipeError(
            f"fit_compensation {fit:g} outside [{lo:g}, {hi:g}]")
    t = state.width
    depth_len = p["depth"] if p["depth"] > 1e-9 else t
    z_top = p["z_top"] if p["z_top"] > 1e-9 else t
    turns = depth_len / pitch
    if turns < THREAD_MIN_TURNS:
        raise RecipeError(
            f"{depth_len:g} deep gives {turns:.1f} turns — needs "
            f"{THREAD_MIN_TURNS:g}")
    major_eff = major + fit
    tdepth = 0.6 * pitch
    minor_d = major_eff - 2.0 * tdepth
    cx, cy = p["cx"], p["cy"]
    through = depth_len >= z_top - 1e-9

    name = op_id or "port"
    state.bores.append(BoreFeature(
        name=f"{name}_minor_bore", axis="Z", d=minor_d,
        center=(cx, cy, 0.0), span=(z_top - depth_len, z_top),
        overshoot=(1.0 if through else 0.0, 1.0)))
    state.threads.append(ThreadFeature(
        name=f"{name}_thread", at=(cx, cy),
        z0=z_top - depth_len, length=depth_len,
        major_d=major_eff, pitch=pitch, internal=True))
    state.datums[f"{name}_axis"] = {
        "at": [cx, cy, z_top], "rotate": [0.0, 0.0, 0.0]}
    state.frame.update({
        f"{name}_thread_major": major_eff,
        f"{name}_thread_pitch": pitch,
        f"{name}_thread_turns": turns,
        f"{name}_thread_fit": fit,
        f"{name}_thread_internal": 1.0,
    })


_register(RecipeOpDecl(
    name="thread_internal_clearance",
    kind="feature",
    params={
        "thread": ("choice", "m20"),
        "fit_compensation": ("length", 0.2),
        "depth": ("length", 0.0),
        "z_top": ("length", 0.0),
        "cx": ("length", 0.0),
        "cy": ("length", 0.0),
    },
    validators=(
        "form.thread_spec_ok",
        "topology.thread_present",
        "topology.bores_open",
    ),
    apply=_thread_internal_clearance,
    description="internally threaded port: minor bore + helical groove, "
                "fit-enlarged so the compensated printed stud mates",
))
