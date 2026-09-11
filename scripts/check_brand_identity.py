"""Impide que las superficies vigentes presenten marcas históricas."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VISIBLE_TARGETS = (
    ROOT / "ats_frontend",
    ROOT / "app" / "api",
    ROOT / "README.md",
    ROOT / "MANUAL_USUARIO.md",
    ROOT / "scripts" / "run_demo.py",
    ROOT / "scripts" / "seed.py",
)
LEGACY_BRAND = re.compile(
    r"\b(?:VERA(?: ATS)?(?![_.-])|PostulaIA|PostulAI)\b", re.IGNORECASE
)


def visible_files() -> list[Path]:
    files: list[Path] = []
    for target in VISIBLE_TARGETS:
        if target.is_file():
            files.append(target)
        elif target.is_dir():
            files.extend(target.rglob("*.py"))
    return files


def main() -> int:
    problems: list[str] = []
    for path in visible_files():
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if LEGACY_BRAND.search(line):
                problems.append(f"{path.relative_to(ROOT)}:{number}: {line.strip()}")
    if problems:
        print("Referencias visibles a marcas heredadas:\n" + "\n".join(problems))
        return 1
    print("Identidad visible verificada: TalentIA")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
