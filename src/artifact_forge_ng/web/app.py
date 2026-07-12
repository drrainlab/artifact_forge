"""The cockpit API. One rule above all: the UI shows what the pipeline
produced. /api/validate is the heart — fast, CAD-free, structured errors
(FindingViewModel), never a traceback.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..archetypes import builder_for
from ..assembly.joints import JOINT_TYPES
from ..catalog.loader import (
    CatalogError,
    compatible_regions,
    load_catalog,
    suggest_region,
)
from ..form.recipe_ops import RECIPE_OPS, RecipeError
from ..pipeline import PipelineFailure, pre_cad_from_instance
from ..product.instance import ProductInstance
from .jobs import ThreadJobRunner
from .serialize import catalog_card_vm, contract_vm, error_finding, preview_vm, validate_vm

REPO_ROOT = Path(__file__).resolve().parents[3]
EXAMPLES_DIR = REPO_ROOT / "catalog" / "examples"
STATIC_DIR = Path(__file__).parent / "static"
OUT_DIR = REPO_ROOT / "out"


def _load_dotenv() -> None:
    """Pick up .env from the repo root (ANTHROPIC_API_KEY etc.) without a
    dotenv dependency. Real environment variables always win."""
    env_file = REPO_ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv()

app = FastAPI(title="Artifact Forge NG — Product Cockpit")
jobs = ThreadJobRunner()


@app.middleware("http")
async def _no_cache_static(request, call_next):
    """ES modules cache aggressively; a local dev cockpit must always
    serve the current code — a stale section renderer is a lie on screen."""
    response = await call_next(request)
    if request.url.path.startswith("/static"):
        response.headers["Cache-Control"] = "no-cache"
    return response


def _cad_available() -> bool:
    try:
        import cadquery  # noqa: F401

        return True
    except Exception:
        return False


def _llm_available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


@app.get("/api/status")
def api_status() -> dict[str, Any]:
    catalog = load_catalog()
    buildable, recipe_only, metadata_only = [], [], []
    for spec in catalog.archetypes.values():
        if spec.form.type == "recipe":
            recipe_only.append(spec.id)
        elif builder_for(spec) is not None:
            buildable.append(spec.id)
        else:
            metadata_only.append(spec.id)
    return {
        "archetypes": {
            "buildable": sorted(buildable),
            "recipe": sorted(recipe_only),
            "metadata_only": sorted(metadata_only),
        },
        "modifiers": sorted(catalog.modifiers),
        "joints": sorted(JOINT_TYPES),
        "recipe_ops": sorted(RECIPE_OPS),
        "features": len(catalog.features),
        "cad": _cad_available(),
        "llm": _llm_available(),
        "strict_default": True,
    }


@app.get("/api/catalog")
def api_catalog() -> dict[str, Any]:
    from collections import Counter

    from ..packs import pack_manifests

    catalog = load_catalog()
    manifests = pack_manifests()
    examples = _examples_index()
    example_counts: Counter[str] = Counter()
    for ex in examples:
        arch = str(ex.get("archetype") or "")
        example_counts[arch.split("@")[0]] += 1

    def _pack_of(spec_id: str) -> tuple[str, str]:
        origin = catalog.origins.get(spec_id, "builtin")
        if origin.startswith("pack:"):
            pid = origin.split(":", 1)[1]
            return pid, str(manifests.get(pid, {}).get("name", pid))
        return ("local", "Local catalog") if origin == "local" else \
               ("core", "Artifact Forge Core")

    cards = []
    for spec in catalog.archetypes.values():
        status = "recipe" if spec.form.type == "recipe" else (
            "buildable" if builder_for(spec) is not None else "metadata_only"
        )
        pack, pack_name = _pack_of(spec.id)
        cards.append(catalog_card_vm(
            spec,
            status=status,
            pack=pack,
            pack_name=pack_name,
            domain=catalog.domains.get(spec.id, "core"),
            source_relpath=catalog.source_relpaths.get(spec.id, ""),
            examples_count=example_counts.get(spec.id, 0),
            regions=[
                {"id": r.id, "role": r.role.value, "editable": r.editable,
                 "label": r.label, "aliases": list(r.aliases),
                 "compatible_modifiers": [
                     mod_id for mod_id in spec.allowed_modifiers
                     if mod_id in catalog.modifiers
                     and any(cr.id == r.id for cr in compatible_regions(
                         spec, catalog.modifiers[mod_id]))
                 ]}
                for r in spec.regions
            ],
        ))

    # featured: pack manifests in load order; unknown ids are a warning,
    # never a crash (a community typo must not kill the cockpit)
    featured: list[str] = []
    for pid, manifest in manifests.items():
        for fid in (manifest.get("catalog") or {}).get("featured", []) or []:
            if fid not in catalog.archetypes:
                import logging

                logging.getLogger(__name__).warning(
                    "pack %r: featured id %r not in catalog — skipped",
                    pid, fid)
                continue
            if fid not in featured:
                featured.append(fid)

    pack_names = {c["pack"]: c["pack_name"] for c in cards}
    pack_tiers = {pid: str(m.get("tier", "free")) for pid, m in manifests.items()}
    facets = {
        "domains": [{"id": d, "count": n} for d, n in sorted(
            Counter(c["domain"] for c in cards).items())],
        "packs": [{"id": p, "name": pack_names[p],
                   "tier": pack_tiers.get(p, "free"), "count": n,
                   "installed": True}
                  for p, n in sorted(Counter(c["pack"] for c in cards).items())],
        "modes": [{"id": m, "count": n} for m, n in sorted(
            Counter(m for c in cards for m in c["modes"]).items())],
        "statuses": [{"id": s, "count": n} for s, n in sorted(
            Counter(c["status"] for c in cards).items())],
    }

    modifiers = [
        {"id": m.id, "category": m.category, "description": m.description.strip(),
         "applies_to": [getattr(r, "value", str(r)) for r in m.applies_to],
         "validators": list(m.validators)}
        for m in catalog.modifiers.values()
    ]
    return {
        "archetypes": sorted(cards, key=lambda c: c["id"]),
        "facets": facets,
        "featured": featured,
        "modifiers": modifiers,
        "joints": [
            {"name": d.name, "description": d.description,
             "cad_checks": list(d.cad_checks)}
            for d in JOINT_TYPES.values()
        ],
        "examples": examples,
    }


#: (id, version, origin) -> PreviewVM | None. Presentation cache only.
_PREVIEW_CACHE: dict[tuple[str, int, str], dict[str, Any] | None] = {}


@app.get("/api/catalog/previews")
def api_catalog_previews(ids: str | None = None) -> dict[str, Any]:
    """Best-effort card previews from the pre-CAD Form IR. No CAD, no LLM,
    no repair/fallback generation; a failed default build is an honest
    null (the UI renders a placeholder). No exception escapes."""
    import logging

    out: dict[str, Any] = {}
    try:
        catalog = load_catalog()
        wanted = set(filter(None, ids.split(","))) if ids else None
        for spec in catalog.archetypes.values():
            if wanted is not None and spec.id not in wanted:
                continue
            key = (spec.id, spec.version, catalog.origins.get(spec.id, ""))
            if key not in _PREVIEW_CACHE:
                try:
                    instance = ProductInstance(
                        schema="product/v1", id=f"preview_{spec.id}",
                        archetype=spec.ref, strict=False)
                    state = pre_cad_from_instance(instance, catalog, False)
                    _PREVIEW_CACHE[key] = (
                        preview_vm(state.form) if state.form is not None
                        and state.form.section is not None else None)
                except Exception:
                    _PREVIEW_CACHE[key] = None
            out[spec.id] = _PREVIEW_CACHE[key]
    except Exception as exc:  # the catalog page must survive a broken preview pass
        logging.getLogger(__name__).warning("previews failed wholesale: %s", exc)
    return out


def _examples_index() -> list[dict[str, Any]]:
    from ..packs import pack_example_dirs

    sources = [("core", p) for p in sorted(EXAMPLES_DIR.glob("*.yaml"))]
    for pack_id, ex_dir in pack_example_dirs():
        sources += [(pack_id, p) for p in sorted(ex_dir.rglob("*.yaml"))]
    out = []
    for source, path in sources:
        try:
            doc = yaml.safe_load(path.read_text()) or {}
        except yaml.YAMLError:
            continue
        kind = str(doc.get("schema", "")).split("/")[0]
        out.append({
            "file": path.name,
            "id": doc.get("id", path.stem),
            "kind": kind,
            "pack": source,
            "archetype": doc.get("archetype"),
            "parts": [p.get("ref") for p in doc.get("parts", [])] or None,
        })
    return out


class YamlBody(BaseModel):
    yaml: str
    strict: bool | None = None


def _load_product(text: str) -> ProductInstance:
    doc = yaml.safe_load(text)
    return ProductInstance.model_validate(doc)


@app.post("/api/validate")
def api_validate(body: YamlBody) -> JSONResponse:
    """The heart of the cockpit: YAML text in, the full truth out —
    CAD-free, so it is fast enough to run on every slider tick."""
    catalog = load_catalog()
    try:
        doc = yaml.safe_load(body.yaml)
    except yaml.YAMLError as exc:
        return _fail([error_finding(f"not valid YAML: {exc}", "schema.yaml")])
    kind = str((doc or {}).get("schema", "")).split("/")[0]
    if kind == "assembly":
        return _validate_assembly(body)
    try:
        instance = ProductInstance.model_validate(doc)
    except Exception as exc:
        return _fail([error_finding(str(exc), "schema.product")])
    try:
        strict = instance.strict if body.strict is None else body.strict
        state = pre_cad_from_instance(instance, catalog, strict)
    except CatalogError as exc:
        return _fail([error_finding(str(exc), "schema.catalog")])
    except PipelineFailure as exc:
        return _fail([error_finding(str(exc), "schema.pipeline")])
    # the recipe kernel's honest refusal (bad svg path, wall too thin…)
    # is a finding the cockpit renders, never a 500 that kills the wizard
    except RecipeError as exc:
        return _fail([error_finding(str(exc), "form.recipe")])
    return JSONResponse(validate_vm(state))


def _validate_assembly(body: YamlBody) -> JSONResponse:
    from ..assembly.pipeline import (
        AssemblyFailure,
        load_assembly,
        run_assembly_validate,
    )
    import tempfile

    try:
        with tempfile.NamedTemporaryFile(
            "w", suffix=".yaml", delete=False
        ) as tmp:
            tmp.write(body.yaml)
            tmp_path = Path(tmp.name)
        try:
            out = run_assembly_validate(tmp_path, body.strict)
        finally:
            tmp_path.unlink(missing_ok=True)
    except AssemblyFailure as exc:
        report = dict(exc.report)
        report["ok"] = False
        return JSONResponse(report)
    except (CatalogError, PipelineFailure) as exc:
        return _fail([error_finding(str(exc), "schema.assembly")])
    out["ok"] = out.get("status") == "pass"
    return JSONResponse(out)


def _fail(findings: list[dict[str, Any]]) -> JSONResponse:
    return JSONResponse({
        "ok": False,
        "status": "fail",
        "findings": findings,
        "form": None,
        "params": [],
        "capability": None,
    })


@app.get("/api/examples/{name}")
def api_example(name: str) -> JSONResponse:
    path = (EXAMPLES_DIR / name).resolve()
    if not str(path).startswith(str(EXAMPLES_DIR.resolve())) or not path.exists():
        return _fail([error_finding(f"unknown example {name!r}", "schema.example")])
    return JSONResponse({"ok": True, "file": name, "yaml": path.read_text()})


# -- jobs: build / edit -------------------------------------------------------


@app.post("/api/build")
def api_build(body: YamlBody) -> dict[str, Any]:
    doc = yaml.safe_load(body.yaml)
    kind = str((doc or {}).get("schema", "")).split("/")[0]

    def run(job) -> Any:
        import tempfile

        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as tmp:
            tmp.write(body.yaml)
            tmp_path = Path(tmp.name)
        try:
            job.log.append(f"building {doc.get('id', '?')} ({kind})")
            if kind == "assembly":
                from ..assembly.pipeline import run_assembly_build

                return run_assembly_build(tmp_path, OUT_DIR, body.strict)
            from ..compiler.pipeline import run_build

            return run_build(tmp_path, OUT_DIR, body.strict)
        finally:
            tmp_path.unlink(missing_ok=True)

    return {"job": jobs.submit("build", run)}


class EditBody(BaseModel):
    yaml: str
    intent: str | None = None
    patch: dict[str, Any] | None = None


def _target_suggestions(patch: dict[str, Any], archetype) -> list[dict[str, Any]]:
    """did-you-mean for modifier targets: for every add/update entry whose
    target is not a region of this archetype, offer the closest real one
    (alias/label resolution first, fuzzy match second). The pipeline never
    silently fixes a patch — it proposes, the user confirms."""
    out: list[dict[str, Any]] = []
    mods = (patch or {}).get("modifiers") or {}
    for key in ("add", "update"):
        for entry in mods.get(key) or []:
            if not isinstance(entry, dict):
                continue
            target = str(entry.get("target") or "")
            if not target or archetype.region(target) is not None:
                continue
            hit = suggest_region(archetype, target)
            if hit is not None:
                out.append({"modifier": entry.get("id"), "given": target,
                            "suggestion": hit.id, "label": hit.label})
    return out


@app.post("/api/edit/preview")
def api_edit_preview(body: EditBody) -> JSONResponse:
    """Pure patch preview: apply the patch, validate the result — NO CAD.
    The user sees the edited YAML and its IR truth before committing."""
    from ..repair.intents import INTENTS, IntentNotApplicable
    from ..repair.patch import Patch, apply_patch

    catalog = load_catalog()
    try:
        instance = _load_product(body.yaml)
        archetype = catalog.archetype_for(instance)
    except Exception as exc:
        return _fail([error_finding(str(exc), "schema.product")])
    try:
        if body.intent:
            spec = INTENTS.get(body.intent)
            if spec is None:
                return _fail([error_finding(
                    f"unknown intent {body.intent!r}; known: {sorted(INTENTS)}",
                    "edit.intent")])
            patch = spec.build_patch(instance, archetype)
        elif body.patch is not None:
            patch = Patch.model_validate({"schema": "patch/v1", **body.patch})
        else:
            return _fail([error_finding("edit needs intent or patch", "edit.input")])
        edited = apply_patch(instance, patch, archetype, catalog)
    # ValueError covers PatchError AND the value grammar's ValueError_ — a
    # patch carrying '-50%' must come back as a finding, never as a 500
    # that leaves the cockpit stuck on "computing patch…"
    except (IntentNotApplicable, ValueError) as exc:
        finding = error_finding(str(exc), "edit.patch")
        did_you_mean = _target_suggestions(body.patch or {}, archetype)
        if did_you_mean:
            finding["suggestion"] = "; ".join(
                f"did you mean region {d['suggestion']!r}"
                + (f" ({d['label']})" if d["label"] else "")
                for d in did_you_mean)
        return JSONResponse({
            "ok": False, "status": "fail", "findings": [finding],
            "form": None, "params": [], "capability": None,
            "did_you_mean": did_you_mean,
        })
    # A valid patch can still change NOTHING (e.g. adding a modifier the
    # instance already carries) — the preview must say so, not let the
    # user "apply" a rebuild of the same object and wonder why.
    noop = (edited.model_dump(by_alias=True, mode="json")
            == instance.model_dump(by_alias=True, mode="json"))
    edited_yaml = yaml.safe_dump(
        edited.model_dump(by_alias=True, mode="json"), sort_keys=False,
        allow_unicode=True,
    )
    validation = api_validate(YamlBody(yaml=edited_yaml, strict=False))
    val = (yaml.safe_load(validation.body.decode())
           if not isinstance(validation, dict) else validation)
    # IR diff of the headline effect: a valid patch can still do the
    # OPPOSITE of the intent (e.g. a bigger edge_margin eating every cell
    # on a narrow band) — the preview must say so BEFORE apply.
    before_val = yaml.safe_load(
        api_validate(YamlBody(yaml=body.yaml, strict=False)).body.decode()
    )
    def _cells(v):
        return [f.get("cells", 0) for f in (v.get("form") or {}).get("fields", [])]
    ir_diff = {"field_cells_before": _cells(before_val),
               "field_cells_after": _cells(val)}
    return JSONResponse({
        "ok": True,
        "patch": patch.model_dump(mode="json"),
        "edited_yaml": edited_yaml,
        "validation": val,
        "ir_diff": ir_diff,
        "noop": noop,
    })


@app.post("/api/edit/apply")
def api_edit_apply(body: EditBody) -> dict[str, Any]:
    def run(job) -> Any:
        import tempfile

        from ..repair.edit import run_edit

        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as tmp:
            tmp.write(body.yaml)
            tmp_path = Path(tmp.name)
        try:
            job.log.append(f"edit: {body.intent or 'patch'}")
            patch_path = None
            if body.patch is not None:
                import json

                pf = tmp_path.with_suffix(".patch.yaml")
                pf.write_text(yaml.safe_dump(
                    {"schema": "patch/v1", **json.loads(json.dumps(body.patch))}
                ))
                patch_path = pf
            return run_edit(tmp_path, OUT_DIR, body.intent, patch_path)
        finally:
            tmp_path.unlink(missing_ok=True)

    return {"job": jobs.submit("edit", run)}


@app.get("/api/jobs/{job_id}")
def api_job(job_id: str) -> JSONResponse:
    job = jobs.get(job_id)
    if job is None:
        return _fail([error_finding(f"unknown job {job_id!r}", "job.unknown")])
    return JSONResponse(job.to_dict())


# -- static -------------------------------------------------------------------

OUT_DIR.mkdir(exist_ok=True)
app.mount("/artifacts", StaticFiles(directory=OUT_DIR), name="artifacts")


def _static_version() -> int:
    """Cache-buster: the newest mtime across the app's own modules — a
    stale renderer must never survive a reload."""
    paths = [STATIC_DIR / "index.html", *(STATIC_DIR / "js").glob("*.js"),
             *(STATIC_DIR / "css").glob("*.css")]
    return int(max(p.stat().st_mtime for p in paths if p.exists()))


@app.get("/")
def index():
    from fastapi.responses import HTMLResponse

    html = (STATIC_DIR / "index.html").read_text().replace(
        "__V__", str(_static_version())
    )
    html = html.replace(
        'href="/static/css/forge.css"',
        f'href="/static/css/forge.css?v={_static_version()}"',
    )
    return HTMLResponse(html, headers={"Cache-Control": "no-cache"})


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def main() -> None:
    import uvicorn
    import webbrowser

    port = int(os.environ.get("FORGE_UI_PORT", "8765"))
    webbrowser.open(f"http://127.0.0.1:{port}")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


# -- svg import: extract path data, flattening layered art if needed ------------


class SvgFlattenBody(BaseModel):
    svg: str
    #: target motif width, mm — tunes the printable-floor opening radius
    motif_w: float = 60.0


@app.post("/api/svg/flatten")
def api_svg_flatten(body: SvgFlattenBody) -> JSONResponse:
    """SVG file text in, ready-to-use ``svg_path`` data out. Single-layer
    files (glyph exports) pass through EXACTLY as authored; layered color
    art is reduced by the luminance painter model (dark = ink raised,
    light = paper cut, background falls away) — which needs the CAD
    backend, once, at import time. The YAML then carries the flattened
    path, so validation stays CAD-free."""
    import re as _re

    from ..form.recipe_ops import RecipeError as _RecipeError
    from ..form.svg_path import svg_path_to_polygons

    if not body.svg.strip():
        return _fail([error_finding("empty svg", "svg.input")])
    ds = _re.findall(r'\bd="([^"]+)"', body.svg)
    if not ds:
        return _fail([error_finding(
            "no <path> elements — convert shapes to paths in the editor",
            "svg.input")])
    joined = " ".join(ds)
    motif_w = max(1.0, float(body.motif_w))
    try:
        outlines, holes, mw = svg_path_to_polygons(joined, motif_w)
        return JSONResponse({
            "ok": True, "path": joined, "flattened": False,
            "outlines": len(outlines), "holes": len(holes),
            "min_width_mm": round(mw, 3),
        })
    except _RecipeError as exc:
        if "path noise" in str(exc):
            # traced art leaves invisible specks and hatch slivers —
            # clean at import time and REPORT the counts; the relief op
            # guard stays strict
            from ..form.recipe_ops_text import MIN_STROKE_ENGRAVE
            from ..form.svg_path import import_svg_path

            try:
                cleaned, info = import_svg_path(
                    joined, motif_w, floor=MIN_STROKE_ENGRAVE)
                outlines, holes, mw = svg_path_to_polygons(cleaned, motif_w)
            except _RecipeError as exc2:
                return _fail([error_finding(str(exc2), "svg.path")])
            return JSONResponse({
                "ok": True, "path": cleaned, "flattened": False,
                "outlines": len(outlines), "holes": len(holes),
                "min_width_mm": round(mw, 3), **info,
            })
        if "OVERLAP" not in str(exc):
            return _fail([error_finding(str(exc), "svg.path")])
    if not _cad_available():
        return _fail([error_finding(
            "layered fills need the CAD backend to flatten — start with "
            "CAD ON, or flatten in your editor (Inkscape: Path → Union)",
            "svg.flatten")])
    try:
        from ..cad.svg_flatten import flatten_svg_layers

        path, info = flatten_svg_layers(body.svg, motif_w=motif_w)
        outlines, holes, mw = svg_path_to_polygons(path, motif_w)
    except _RecipeError as exc:
        return _fail([error_finding(str(exc), "svg.flatten")])
    return JSONResponse({
        "ok": True, "path": path, "flattened": True,
        "outlines": len(outlines), "holes": len(holes),
        "min_width_mm": round(mw, 3), "info": info,
    })


# -- intent / natural edit (the LLM seam; deterministic fallback) ---------------


class IntentBody(BaseModel):
    prompt: str


@app.post("/api/intent")
def api_intent(body: IntentBody) -> JSONResponse:
    from . import intent, llm

    catalog = load_catalog()
    if not body.prompt.strip():
        return _fail([error_finding("empty prompt", "intent.input")])
    if llm.available():
        try:
            return JSONResponse(intent.llm_intent(body.prompt, catalog))
        except RuntimeError as exc:
            out = intent.deterministic_intent(body.prompt, catalog)
            out["notes"] = f"{exc}; deterministic fallback"
            return JSONResponse(out)
    return JSONResponse(intent.deterministic_intent(body.prompt, catalog))


class NlEditBody(BaseModel):
    yaml: str
    text: str
    #: Region the user selected in the UI (viewport click / picker) — pins
    #: the target enum the LLM sees.
    selected_region: str | None = None


@app.post("/api/nl_edit")
def api_nl_edit(body: NlEditBody) -> JSONResponse:
    from . import intent, llm

    if not body.text.strip():
        return _fail([error_finding(
            "empty edit request — describe the change or pick an intent "
            "button", "edit.input")])
    if not llm.available():
        # honest degraded mode: map to a known intent by keyword
        text = body.text.lower()
        for key, name in (
            ("поддерж", "make_support_free"), ("support", "make_support_free"),
            ("прочн", "make_stronger"), ("strong", "make_stronger"),
            ("устойчив", "make_stronger"),
            ("биом", "make_biomorphic"), ("органич", "make_biomorphic"),
            ("bio", "make_biomorphic"),
            ("перфор", "remove_perforation"), ("perfor", "remove_perforation"),
        ):
            if key in text:
                return JSONResponse({"ok": True, "intent": name, "patch": None,
                                     "source": "deterministic"})
        return _fail([error_finding(
            "LLM OFF and no known intent matched — use an intent button or a "
            "patch", "edit.nl")])
    try:
        catalog = load_catalog()
        instance = _load_product(body.yaml)
        archetype = catalog.archetype_for(instance)
        return JSONResponse(intent.nl_edit(
            body.text, body.yaml, archetype, catalog,
            selected_region=body.selected_region))
    except RuntimeError as exc:
        return _fail([error_finding(str(exc), "edit.llm")])
    except Exception as exc:  # noqa: BLE001 — structured, never a traceback
        return _fail([error_finding(str(exc), "edit.nl")])


# -- prompt -> assembly (wave W3): creative composition over the catalog ---------


class AssemblyIntentBody(BaseModel):
    prompt: str
    #: optional user-attached SVG (full document or raw path data) —
    #: cleaned at intake; the model references it as "@svg", the server
    #: substitutes the real path data at expansion
    svg: str | None = None


@app.post("/api/assembly/intent", response_model=None)
def api_assembly_intent(body: AssemblyIntentBody) -> JSONResponse | dict[str, Any]:
    """Compose a multi-part assembly from a text prompt. Always an async
    job (2-3 LLM calls + up to 3 CAD-free validations): poll
    /api/jobs/{id}. The result carries the three-tier verification state
    (failed / pre_cad_pass / build_required) — the draft YAML then flows
    through the ordinary /api/validate and /api/build unchanged."""
    from ..form.recipe_ops import RecipeError as _RecipeError
    from . import assembly_intent, llm

    if not body.prompt.strip():
        return _fail([error_finding("empty prompt", "assembly.intent.input")])
    catalog = load_catalog()
    prompt = body.prompt
    svg_asset, svg_summary = None, ""
    if body.svg and body.svg.strip():
        try:
            svg_asset, svg_summary = assembly_intent.prepare_svg_asset(
                body.svg)
        except _RecipeError as exc:
            # a broken asset fails the request up front — no LLM calls
            return _fail([error_finding(str(exc), "assembly.intent.svg")])

    def run(job: Any) -> Any:
        if not llm.available():
            job.log.append("LLM OFF — deterministic suggestions only")
            return assembly_intent.deterministic_assembly(prompt, catalog)
        try:
            return assembly_intent.llm_assembly(
                prompt, catalog, progress=job.log.append,
                svg_asset=svg_asset, svg_summary=svg_summary)
        except RuntimeError as exc:
            job.log.append(f"LLM failed: {exc} — deterministic fallback")
            out = assembly_intent.deterministic_assembly(prompt, catalog)
            out["notes"] = f"{exc}; deterministic fallback"
            return out

    return {"job": jobs.submit("assembly_intent", run)}
