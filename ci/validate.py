"""Validates the static assets before they are tagged and served.

Run from the repository root (CI: the Jenkins job PrefKB-KBStorage/KB_STATIC_ASSETS):

    pip install usd-core==26.5
    python ci/validate.py

Checks, all of which must pass:
  - every USD layer (.usd / .usda / .usdc) opens, composes without errors and
    has every asset it depends on (sublayers, references, MDL, textures)
    resolvable from the repo;
  - every JSON file parses;
  - every Python file compiles.

usd-core is pinned to the version the KB_PBR_Processor image ships.
Exit code 0 = valid, 1 = something is broken (each problem is printed).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
USD_SUFFIXES = {".usd", ".usda", ".usdc"}
# MDL modules the renderer (Omniverse Kit) ships on its own search path: the
# stages reference them by bare name and they are never files in this repo.
RENDERER_MDL = {"OmniPBR.mdl", "OmniPBR_ClearCoat.mdl", "OmniGlass.mdl", "OmniSurface.mdl"}


def tracked_files() -> list[Path]:
    return sorted(
        p for p in ROOT.rglob("*")
        if p.is_file() and ".git" not in p.relative_to(ROOT).parts and "ci" != p.relative_to(ROOT).parts[0]
    )


def check_usd(path: Path) -> list[str]:
    from pxr import Usd, UsdUtils

    problems: list[str] = []
    stage = Usd.Stage.Open(str(path))
    if stage is None:
        return [f"{path}: USD cannot open it"]
    for err in stage.GetCompositionErrors():
        problems.append(f"{path}: composition error: {err}")
    _layers, _assets, unresolved = UsdUtils.ComputeAllDependencies(str(path))
    for missing in unresolved:
        if Path(missing).name in RENDERER_MDL and Path(missing).name == missing:
            continue
        problems.append(f"{path}: unresolved dependency: {missing}")
    return problems


def check_json(path: Path) -> list[str]:
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        return [f"{path}: invalid JSON: {exc}"]
    return []


def check_python(path: Path) -> list[str]:
    # compile() and not py_compile: nothing is written next to the sources.
    try:
        compile(path.read_bytes(), str(path), "exec")
    except (SyntaxError, ValueError) as exc:
        return [f"{path}: Python does not compile: {exc}"]
    return []


def main() -> int:
    problems: list[str] = []
    counts = {"usd": 0, "json": 0, "python": 0}
    for path in tracked_files():
        suffix = path.suffix.lower()
        if suffix in USD_SUFFIXES:
            counts["usd"] += 1
            problems += check_usd(path)
        elif suffix == ".json":
            counts["json"] += 1
            problems += check_json(path)
        elif suffix == ".py":
            counts["python"] += 1
            problems += check_python(path)

    print(f"validated: {counts['usd']} USD, {counts['json']} JSON, {counts['python']} Python")
    if counts["usd"] == 0:
        problems.append("no USD layer found: the validation checked nothing")
    for problem in problems:
        print(f"ERROR {problem}")
    print("OK" if not problems else f"{len(problems)} problem(s)")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
