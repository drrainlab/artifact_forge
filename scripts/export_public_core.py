#!/usr/bin/env python3
"""Deterministic export of the public open-core tree.

Builds a clean copy of the core engine — everything the public
`artifact-forge` repository ships and nothing else — and writes an
export_manifest.json recording exactly what went in.

Usage:
    python scripts/export_public_core.py <target-dir> [--force]

The target must not exist (or pass --force to replace it). The private
monorepo stays untouched; the export is a fresh tree for a fresh-history
public repository.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

#: Directories and files copied verbatim (relative to the repo root).
INCLUDE = [
    "src/artifact_forge_ng",
    "tests",
    "catalog/examples",
    "docs/ARCHITECTURE.md",
    "docs/VALIDATION.md",
    "docs/BUILDERS.md",
    "docs/BIOMORPHIC.md",
    "README.md",
    "LICENSE",
    "THIRD_PARTY_NOTICES.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "CHANGELOG.md",
    ".github/workflows/ci.yml",
    ".gitignore",
    ".env.example",
    "pyproject.toml",
]

#: Never exported, wherever they appear (glob against the relative path).
EXCLUDE_PATTERNS = [
    "packs/*",
    "baselines/*",          # private dev artifacts — always excluded
    "docs/ROADMAP.md",
    "docs/ECOSYSTEM.md",
    "docs/VERTICAL_FARM_PACK.md",
    "docs/domains/*",
    "catalog/local/*",
    ".env",
    ".env.*",
    ".claude/*",
    ".vscode/*",
    "out/*",
    "uv.lock",              # workspace lock references private members
    "*.pyc",
    "__pycache__/*",
    ".DS_Store",
    ".pytest_cache/*",
]

#: Explicitly allowed despite matching an exclude pattern.
ALLOW = {".env.example"}

#: The private paths whose absence the smoke test asserts.
MUST_NOT_EXIST = [
    "packs",
    "baselines",
    "docs/ROADMAP.md",
    "docs/ECOSYSTEM.md",
    "docs/VERTICAL_FARM_PACK.md",
    "docs/domains",
    "catalog/local",
    "catalog/examples/vertical_farm",
    ".env",
    "uv.lock",
]


def _copy_tree(src: Path, dst: Path, rel_base: str, files: list[str]) -> None:
    for p in sorted(src.rglob("*")):
        rel = f"{rel_base}/{p.relative_to(src)}" if rel_base else str(p.relative_to(src))
        if p.is_dir():
            continue
        if any(part in ("__pycache__", ".pytest_cache") for part in p.parts):
            continue
        if p.name in (".DS_Store",) or p.suffix == ".pyc":
            continue
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, target)
        files.append(rel)


def _transform_pyproject(target: Path) -> None:
    """The public pyproject must not reference the private workspace."""
    p = target / "pyproject.toml"
    s = p.read_text()
    s = s.replace(
        '    # private dev monorepo: the VF pack rides in the dev venv so the full\n'
        '    # (core + pack) suite runs; the public core never depends on it\n'
        '    "artifact-forge-vf",\n', "")
    s = re.sub(r"\n\[tool\.uv\.workspace\]\nmembers = \[[^\]]*\]\n", "\n", s)
    s = re.sub(r"\n\[tool\.uv\.sources\]\nartifact-forge-vf = \{[^}]*\}\n", "\n", s)
    s = s.replace('testpaths = ["tests", "packs/artifact-forge-vf/tests"]',
                  'testpaths = ["tests"]')
    assert "artifact-forge-vf" not in s and "packs/" not in s
    p.write_text(s)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("target", type=Path)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    target: Path = args.target.resolve()
    if target.exists():
        if not args.force:
            print(f"refusing to overwrite {target} (use --force)", file=sys.stderr)
            return 2
        shutil.rmtree(target)
    target.mkdir(parents=True)

    files: list[str] = []
    for entry in INCLUDE:
        src = REPO / entry
        if not src.exists():
            print(f"missing include: {entry}", file=sys.stderr)
            return 3
        if src.is_dir():
            _copy_tree(src, target, entry, files)
        else:
            (target / entry).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target / entry)
            files.append(entry)

    _transform_pyproject(target)

    # belt and braces: nothing excluded may have slipped in via a dir copy
    leaked = [f for f in files if f not in ALLOW
              for pat in EXCLUDE_PATTERNS if fnmatch.fnmatch(f, pat)]
    for rel in MUST_NOT_EXIST:
        if (target / rel).exists():
            leaked.append(rel)
    if leaked:
        print("EXPORT LEAK:", sorted(set(leaked)), file=sys.stderr)
        return 4

    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                            capture_output=True, text=True).stdout.strip()
    vm = re.search(r'^version = "([^"]+)"',
                   (REPO / "pyproject.toml").read_text(), re.M)
    assert vm is not None, "version missing from pyproject.toml"
    version = vm.group(1)
    manifest = {
        "source_commit": commit,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "artifact_forge_version": version,
        "included_files": sorted(files),
        "excluded_patterns": EXCLUDE_PATTERNS,
        "excluded_private_paths": MUST_NOT_EXIST,
    }
    (target / "export_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n")
    print(f"exported {len(files)} files to {target} @ {commit[:7]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
