"""Joint grounding declarations stay coherent with their ir_check bodies.

The declarations (JointDecl.params / side_a / side_b) are grounding
metadata for the assembly digest — never executed. This test is the
honesty gate: a declaration that names a param or frame key the ir_check
does not actually read (or misses one it does) fails here. Heuristic by
design — regexes over ``inspect.getsource`` — cheap and it catches the
drift that matters.
"""

from __future__ import annotations

import inspect
import re

import pytest

from artifact_forge_ng.assembly.joints import JOINT_TYPES
from artifact_forge_ng.catalog.loader import load_catalog

load_catalog()  # pack joints register on catalog load

#: Joints whose grounding declaration is not written yet. SHRINK-ONLY:
#: adding a name here is forbidden; wave G2 emptied it.
UNDECLARED: set[str] = set()

_PARAM_GET = re.compile(r"""joint\.params\.get\(\s*["'](\w+)["']""")
_PLACEHOLDER = re.compile(r"\{\w+\}")


def _declared():
    return {
        name: decl
        for name, decl in JOINT_TYPES.items()
        if name not in UNDECLARED
    }


def _sources(decl):
    fn_src = inspect.getsource(decl.ir_check)
    module = inspect.getmodule(decl.ir_check)
    mod_src = inspect.getsource(module) if module else fn_src
    return fn_src, mod_src


def test_undeclared_allowlist_is_current():
    """Every registered joint is either declared or on the allowlist —
    and the allowlist holds no stale names."""
    missing = {
        n for n, d in JOINT_TYPES.items()
        if not d.params and d.side_a is None and d.side_b is None
    }
    assert missing == (UNDECLARED & set(JOINT_TYPES)), (
        f"declaration gap drifted: undeclared in registry {sorted(missing)} "
        f"vs allowlist {sorted(UNDECLARED & set(JOINT_TYPES))}"
    )


@pytest.mark.parametrize("name", sorted(_declared()))
def test_declared_params_match_ir_check(name):
    decl = JOINT_TYPES[name]
    fn_src, _ = _sources(decl)
    in_source = set(_PARAM_GET.findall(fn_src))
    declared = {p.name for p in decl.params}
    assert declared == in_source, (
        f"{name}: declared params {sorted(declared)} != params the ir_check "
        f"reads {sorted(in_source)}"
    )


@pytest.mark.parametrize("name", sorted(_declared()))
def test_declared_side_requirements_appear_in_source(name):
    decl = JOINT_TYPES[name]
    fn_src, mod_src = _sources(decl)

    def present(literal: str) -> bool:
        cleaned = _PLACEHOLDER.sub("", literal)
        return cleaned in fn_src or cleaned in mod_src

    for side_name, side in (("side_a", decl.side_a), ("side_b", decl.side_b)):
        if side is None:
            continue
        for key in side.frame_keys:
            assert present(key), (
                f"{name}.{side_name}: frame key {key!r} not found in the "
                "ir_check source — declaration drifted"
            )
        for attr in ("bores_prefix", "pins_prefix", "ribs_prefix",
                     "cutboxes_contains"):
            literal = getattr(side, attr)
            if literal:
                assert present(literal), (
                    f"{name}.{side_name}: {attr}={literal!r} not found in "
                    "the ir_check source — declaration drifted"
                )


@pytest.mark.parametrize("name", sorted(JOINT_TYPES))
def test_pose_mode_is_legal(name):
    assert JOINT_TYPES[name].pose_mode in {"establish", "verify", "either"}


def test_interface_frame_keys_agree_with_joint_declarations():
    """An interface type that names frame_keys must be realized by joints
    whose side declarations know those keys' families — the two registries
    describe ONE contract."""
    from artifact_forge_ng.product.interfaces import INTERFACE_TYPES

    # Interface types whose frame keys legitimately describe a DIFFERENT
    # aspect than their realizing joint measures (the socket geometry vs
    # the snap-beam mechanics) — reviewed, not drift.
    disjoint_ok = {"cylindrical_payload_socket"}

    checked = 0
    for itype in INTERFACE_TYPES.values():
        if not itype.frame_keys or not itype.joints:
            continue
        if itype.name in disjoint_ok:
            continue
        iface_keys = {k for keys in itype.frame_keys.values() for k in keys}
        joint_keys: set[str] = set()
        for jname in itype.joints:
            decl = JOINT_TYPES.get(jname)
            if decl is None:
                continue
            for side in (decl.side_a, decl.side_b):
                if side is not None:
                    joint_keys.update(
                        _PLACEHOLDER.sub("", k) for k in side.frame_keys)
        if not joint_keys:
            continue
        checked += 1
        overlap = {k for k in iface_keys if any(
            k in jk or jk in k for jk in joint_keys)}
        assert overlap or not iface_keys, (
            f"interface {itype.name}: frame_keys {sorted(iface_keys)} share "
            f"nothing with its joints' declarations {sorted(joint_keys)}"
        )
    assert checked, "no interface type exercised the cross-check"


def test_param_defaults_match_ir_check_defaults():
    """Spot-check: declared defaults agree with the literal defaults the
    ir_check passes to params.get. Regex-extracted, string-compared."""
    pattern = re.compile(
        r"""joint\.params\.get\(\s*["'](\w+)["']\s*,\s*([^)\n]+)\)""")
    for name, decl in _declared().items():
        fn_src, _ = _sources(decl)
        source_defaults = dict(pattern.findall(fn_src))
        module_globals = getattr(decl.ir_check, "__globals__", {})
        for p in decl.params:
            if p.name not in source_defaults or p.default is None:
                continue
            literal = source_defaults[p.name].strip().strip('"\'')
            # the ir_check may name a module constant (PILOT_PREFIX)
            resolved = str(module_globals.get(literal, literal))
            assert str(p.default) in resolved or resolved in str(p.default), (
                f"{name}.{p.name}: declared default {p.default!r} vs "
                f"ir_check default {resolved!r}"
            )
