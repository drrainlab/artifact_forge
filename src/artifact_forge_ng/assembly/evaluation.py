"""Incremental assembly evaluation — per-job memoization (wave W1b).

The intent repair loop re-validates near-identical assemblies up to three
times per job; a flagship-sized assembly is ~8 pre-CAD part builds a pass.
Between attempts the model usually changes one datum, one joint or one
part's params — everything else is recomputable from cache.

``AssemblyEvaluationSession`` wraps the ordinary CAD-free validation with
content-addressed memoization:

* part pre-CAD states — keyed by the part's EFFECTIVE content (params
  AFTER shared materialization, modifiers, manufacturing, strict), never
  by ``ref`` or instance id: two identical sections share one Form IR;
* joint IR results — keyed by joint type/params/rotate + both parts'
  content fingerprints and datum anchors;
* deterministic failures are cached too (a PipelineFailure re-raises).

Cached objects are treated as immutable — nothing downstream mutates a
``PipelineState``; part summaries are materialized per call with the
actual instance id, so a shared state never leaks another part's name.
The cache is in-memory, bounded, thread-confined: one session per intent
job, dropped with it — no stale-catalog problems by construction.

This is deliberately NOT a generic DAG engine: the graph stays implicit
in the call structure; ``pipeline.validate_assembly_doc`` remains a thin
one-pass facade over a fresh session (the parity test pins that).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from ..catalog.loader import Catalog
from ..core.findings import Finding
from ..pipeline import PipelineState, pre_cad_from_instance
from ..product.assembly import AssemblyInstance, JointUse
from ..product.instance import ProductInstance


def stable_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


class EvaluationCache:
    """Bounded FIFO map. Values are (kind, payload) where kind is
    "ok" or "raise" — deterministic failures replay honestly."""

    def __init__(self, max_entries: int = 512) -> None:
        self.max_entries = max_entries
        self._data: dict[str, tuple[str, Any]] = {}

    def get(self, key: str) -> tuple[str, Any] | None:
        return self._data.get(key)

    def put(self, key: str, kind: str, payload: Any) -> None:
        if len(self._data) >= self.max_entries:
            self._data.pop(next(iter(self._data)))
        self._data[key] = (kind, payload)


class AssemblyEvaluationSession:
    """One session per async intent job. ``validate`` mirrors
    ``pipeline.validate_assembly_doc`` exactly, with memoized nodes;
    ``last_stats`` carries cache hit/miss counts for the job log."""

    def __init__(self, catalog: Catalog, *,
                 cache: EvaluationCache | None = None) -> None:
        self.catalog = catalog
        self.cache = cache or EvaluationCache()
        # the catalog cannot change under a session; a DIFFERENT loaded
        # catalog object is a different fingerprint -> full cache miss
        self._catalog_fp = f"cat{id(catalog):x}"
        self._form_fp: dict[int, str] = {}   # id(PartForm) -> part key
        self.last_stats: dict[str, int] = {}

    # -- memoized nodes ----------------------------------------------------

    def _part_key(self, inst: ProductInstance, strict: bool) -> str:
        content = inst.model_dump(by_alias=True, mode="json", exclude={"id"})
        return "part:" + stable_hash(
            {"catalog": self._catalog_fp, "strict": strict, "inst": content})

    def part_state(self, inst: ProductInstance, strict: bool) -> PipelineState:
        key = self._part_key(inst, strict)
        hit = self.cache.get(key)
        if hit is not None:
            self.last_stats["parts_cached"] += 1
            kind, payload = hit
            if kind == "raise":
                raise payload
            state: PipelineState = payload
        else:
            self.last_stats["parts_built"] += 1
            try:
                state = pre_cad_from_instance(inst, self.catalog, strict)
            except Exception as exc:
                self.cache.put(key, "raise", exc)
                raise
            self.cache.put(key, "ok", state)
        if state.form is not None:
            self._form_fp[id(state.form)] = key
        return state

    def _ir_eval(self, decl, joint: JointUse, form_a, form_b,
                 pose) -> list[Finding]:
        fp_a = self._form_fp.get(id(form_a), "?a")
        fp_b = self._form_fp.get(id(form_b), "?b")
        key = "joint:" + stable_hash({
            "type": joint.type, "params": joint.params,
            "rotate": list(joint.rotate),
            "a": [fp_a, joint.a_datum], "b": [fp_b, joint.b_datum],
        })
        hit = self.cache.get(key)
        if hit is not None:
            self.last_stats["joints_cached"] += 1
            return list(hit[1])
        self.last_stats["joints_checked"] += 1
        findings = decl.ir_check(form_a, form_b, pose, joint)
        self.cache.put(key, "ok", list(findings))
        return list(findings)

    # -- the one-pass validation over memoized nodes -------------------------

    def validate(self, asm: AssemblyInstance, *,
                 strict_flag: bool | None) -> dict[str, Any]:
        from ..core.findings import Status
        from .pipeline import (AssemblyFailure, _inject_shared,
                               _joint_findings, validate_assembly)

        self.last_stats = {"parts_built": 0, "parts_cached": 0,
                           "joints_checked": 0, "joints_cached": 0}
        strict = asm.strict if strict_flag is None else strict_flag
        validate_assembly(asm, self.catalog)
        instances = _inject_shared(asm, self.catalog)
        states = {
            ref: self.part_state(inst, strict)
            for ref, inst in instances.items()
        }
        joint_findings, _, pose_report = _joint_findings(
            asm, states, ir_eval=self._ir_eval)

        parts_summary = {}
        for ref, st in states.items():
            s = st.summary()
            # a cache-shared state carries the FIRST instance's id —
            # materialize the actual part id on emission
            s["product"] = instances[ref].id
            parts_summary[ref] = s
        critical_joint = [
            f for f in joint_findings
            if f.critical and f.status is Status.FAIL
        ]
        status = "fail" if critical_joint or any(
            s["status"] == "fail" for s in parts_summary.values()
        ) else "pass"
        out: dict[str, Any] = {
            "assembly": asm.id,
            "root": asm.root,
            "parts": parts_summary,
            "assembly_pose": pose_report,
            "joints": [f.to_dict() for f in joint_findings],
            "status": status,
        }
        if asm.meta:
            out["meta"] = dict(asm.meta)
        if strict:
            for st in states.values():
                st.enforce_strict()
            if critical_joint:
                raise AssemblyFailure(
                    out,
                    "strict: joint failures: "
                    + ", ".join(f.check for f in critical_joint),
                    code=4,
                )
        return out

    def stats_line(self, attempt: int) -> str:
        s = self.last_stats
        return (f"validate attempt {attempt}: parts "
                f"{s.get('parts_cached', 0)} cached / "
                f"{s.get('parts_built', 0)} rebuilt, joints "
                f"{s.get('joints_cached', 0)} cached / "
                f"{s.get('joints_checked', 0)} rechecked")
