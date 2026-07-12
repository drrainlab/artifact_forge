"""The forge CLI.

``forge validate product.yaml``
    Everything up to (and excluding) CAD: catalog load, instance
    cross-validation, parameter resolution, capability report, Form IR
    build, form validators. Prints the form_checks block and exits non-zero
    on any critical failure (strict mode) — the golden gate before any CAD.

``forge build product.yaml [-o out/]``
    All of the above, then CAD compilation, geometry validators, honesty
    report and STL/STEP export.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

from .catalog.loader import CatalogError
from .pipeline import PipelineFailure, run_pre_cad


def _schema_kind(path: Path) -> str:
    """Peek at the document's ``schema:`` marker — ``forge validate|build``
    accept single products AND assemblies through the same commands."""
    doc = yaml.safe_load(Path(path).read_text())
    marker = (doc or {}).get("schema", "")
    return str(marker).split("/")[0]


def run_validate(
    product_path: Path,
    strict_flag: bool | None,
    *,
    debug_ir: bool = False,
    out_dir: Path = Path("out"),
) -> dict[str, Any]:
    state = run_pre_cad(product_path, strict_flag)
    out = state.summary()
    if (
        debug_ir
        and state.form is not None
        and state.form.exoskeleton is not None
    ):
        # Opt-in only: a plain validate writes NOTHING to disk.
        from .form.exoskeleton.debug import dump_exoskeleton_debug

        written = dump_exoskeleton_debug(state.form, out_dir / state.instance.id)
        out["debug_ir"] = [str(p) for p in written]
    try:
        state.enforce_strict()
    except PipelineFailure:
        _print(out)
        raise
    return out


def _print(doc: dict[str, Any]) -> None:
    yaml.safe_dump(doc, sys.stdout, sort_keys=False, allow_unicode=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="forge")
    sub = parser.add_subparsers(dest="command", required=True)

    p_validate = sub.add_parser("validate", help="validate a product YAML without CAD")
    p_validate.add_argument("product", type=Path)
    p_validate.add_argument("--strict", action="store_true", default=None)
    p_validate.add_argument(
        "--debug-ir", action="store_true",
        help="dump exoskeleton IR debug JSONs to <out>/<product-id>/",
    )
    p_validate.add_argument("-o", "--out", type=Path, default=Path("out"))

    p_build = sub.add_parser("build", help="build a product to STL/STEP")
    p_build.add_argument("product", type=Path)
    p_build.add_argument("-o", "--out", type=Path, default=Path("out"))
    p_build.add_argument("--strict", action="store_true", default=None)

    p_edit = sub.add_parser(
        "edit",
        help="semantic edit: apply an intent/patch, rebuild, verify preserve",
    )
    p_edit.add_argument("product", type=Path)
    p_edit.add_argument("--intent", type=str, default=None)
    p_edit.add_argument("--patch", type=Path, default=None)
    p_edit.add_argument("-o", "--out", type=Path, default=Path("out"))

    sub.add_parser("ui", help="launch the Product Cockpit (local web)")

    p_compat = sub.add_parser(
        "compat",
        help="derived interface compatibility matrix of the whole catalog",
    )
    p_compat.add_argument(
        "--yaml", action="store_true",
        help="emit the raw matrix as YAML instead of the table",
    )

    p_audit = sub.add_parser(
        "audit",
        help="datum-declaration honesty audit: declared vs built Form IR",
    )
    p_audit.add_argument(
        "--all", action="store_true",
        help="also report archetypes that publish datums but declare none",
    )

    p_digest = sub.add_parser(
        "digest",
        help="inspect what the assembly-intent LLM actually sees for a "
             "prompt: candidates + the grounding digest",
    )
    p_digest.add_argument("prompt", help="the user prompt to ground")
    p_digest.add_argument(
        "--candidates-only", action="store_true",
        help="print only the retrieval result, not the full digest text",
    )

    args = parser.parse_args(argv)
    try:
        if args.command == "digest":
            from .catalog.grounding import (assembly_digest,
                                            select_assembly_candidates)
            from .catalog.loader import load_catalog

            catalog = load_catalog()
            ids = select_assembly_candidates(args.prompt, catalog)
            print(f"candidates ({len(ids)}):")
            for aid in ids:
                print(f"  - {aid}")
            if not args.candidates_only:
                print()
                print(assembly_digest(catalog, part_ids=ids))
            return 0
        if args.command == "audit":
            from .catalog.audit import audit_catalog_datums
            from .catalog.loader import load_catalog

            audits = audit_catalog_datums(
                load_catalog(), only_declared=not args.all)
            failed = False
            for a in audits:
                for w in a.warnings:
                    print(f"WARN {a.archetype}: {w}")
                for p in a.problems:
                    print(f"FAIL {a.archetype}: {p}")
                    failed = True
            ok = sum(1 for a in audits if a.ok)
            print(f"audited {len(audits)} archetype(s): {ok} ok, "
                  f"{len(audits) - ok} with problems")
            return 4 if failed else 0
        if args.command == "compat":
            from .catalog.compat import compat_matrix, render_compat

            matrix = compat_matrix()
            if args.yaml:
                _print(matrix)
            else:
                print(render_compat(matrix))
            return 0
        if args.command == "validate":
            if _schema_kind(args.product) == "assembly":
                from .assembly.pipeline import run_assembly_validate

                _print(run_assembly_validate(args.product, args.strict))
                return 0
            _print(run_validate(
                args.product, args.strict,
                debug_ir=args.debug_ir, out_dir=args.out,
            ))
            return 0
        if args.command == "build":
            if _schema_kind(args.product) == "assembly":
                from .assembly.pipeline import run_assembly_build

                _print(run_assembly_build(args.product, args.out, args.strict))
                return 0
            from .compiler.pipeline import run_build

            _print(run_build(args.product, args.out, args.strict))
            return 0
        if args.command == "edit":
            from .repair.edit import run_edit

            _print(run_edit(args.product, args.out, args.intent, args.patch))
            return 0
        if args.command == "ui":
            from .web.app import main as ui_main

            ui_main()
            return 0
    except PipelineFailure as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return exc.code
    except CatalogError as exc:
        print(f"CATALOG ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
