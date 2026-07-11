"""Demo form check — replace with your measured semantics.

The pattern: read the frame keys / features your ops publish, honestly
return n/a when they are absent, FAIL with the measured number when the
geometry breaks the promise."""
from __future__ import annotations

from artifact_forge_ng.core.findings import Finding
from artifact_forge_ng.form.checks_common import make_finding
from artifact_forge_ng.form.part import PartForm
from artifact_forge_ng.validators.probes import register_probe

_finding = make_finding

EDGE_MARGIN_MIN = 3.0  # mm


def check_example_edge_margin_ok(form: PartForm) -> Finding:
    check = "form.example_edge_margin_ok"
    f = form.frame
    if "outline_u1" not in f or not form.holes:
        return _finding(check, True, "n/a — no plate outline or holes",
                        critical=False)
    from artifact_forge_ng.core.fasteners import screw_spec

    worst = min(
        min(f["outline_u1"] - abs(h.at[0]), f["outline_v1"] - abs(h.at[1]))
        - screw_spec(h.screw)["clear"] / 2.0
        for h in form.holes)
    ok = worst >= EDGE_MARGIN_MIN
    return _finding(
        check, ok,
        f"worst hole-to-edge margin {worst:.2f} "
        f"{'>=' if ok else '<'} {EDGE_MARGIN_MIN:g}",
        measured=worst, limit=EDGE_MARGIN_MIN)


register_probe("form.example_edge_margin_ok")(
    lambda form, ctx: check_example_edge_margin_ok(form))
