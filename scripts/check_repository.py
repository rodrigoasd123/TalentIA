"""Bloquea secretos y artefactos locales antes de publicar."""
from __future__ import annotations
import re
import subprocess
from pathlib import Path

FORBIDDEN_PARTS = {
    ".env", ".talentia-backups", ".talentia_dev_key", ".vera_dev_key",
    "__pycache__", ".pytest_cache", ".pytest-tmp", "storage",
}
FORBIDDEN_SUFFIXES = {".pyc", ".pyo", ".db", ".sqlite", ".sqlite3", ".db-shm", ".db-wal"}
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"AIzaSy[0-9A-Za-z_-]{33}"),
    re.compile(r"AQ\.[0-9A-Za-z_-]{30,}"),
    re.compile(r"ghp_[0-9A-Za-z]{30,}"),
    re.compile(r"sk-[0-9A-Za-z_-]{30,}"),
)


def candidate_files() -> list[Path]:
    output = subprocess.check_output(
        ["git", "-c", f"safe.directory={Path.cwd().as_posix()}", "ls-files", "--cached", "--others", "--exclude-standard"],
        text=True,
    )
    return [Path(line) for line in output.splitlines() if line.strip()]


def main() -> int:
    files = candidate_files()
    problems: list[str] = []
    for path in files:
        if any(part in FORBIDDEN_PARTS for part in path.parts) or any(path.name.endswith(suffix) for suffix in FORBIDDEN_SUFFIXES):
            problems.append(f"artefacto prohibido: {path}")
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if any(pattern.search(content) for pattern in SECRET_PATTERNS):
            problems.append(f"posible secreto: {path}")
    if problems:
        print("\n".join(problems))
        return 1
    print(f"Repositorio seguro: {len(files)} archivos revisados")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
