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


def run_validate(product_path: Path, strict_flag: bool | None) -> dict[str, Any]:
    state = run_pre_cad(product_path, strict_flag)
    out = state.summary()
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

    p_build = sub.add_parser("build", help="build a product to STL/STEP")
    p_build.add_argument("product", type=Path)
    p_build.add_argument("-o", "--out", type=Path, default=Path("out"))
    p_build.add_argument("--strict", action="store_true", default=None)

    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            _print(run_validate(args.product, args.strict))
            return 0
        if args.command == "build":
            from .compiler.pipeline import run_build

            _print(run_build(args.product, args.out, args.strict))
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
