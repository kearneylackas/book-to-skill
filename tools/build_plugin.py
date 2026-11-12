#!/usr/bin/env python3
"""Package book-to-skill as an installable Claude plugin (a ``.plugin`` zip).

The repository stays an Agent Skills checkout; this tool only *assembles* a
plugin from it, so nothing about the existing per-host installs changes:

    <name>.plugin
    ├── .claude-plugin/plugin.json
    ├── README.md
    ├── LICENSE.md
    └── skills/book-to-skill/
        ├── SKILL.md            (the converter spec, unchanged)
        ├── LICENSE.md
        ├── scripts/extract.py  (extractor entrypoint)
        ├── book_to_skill/      (extractor package)
        └── tools/              (validate_skill.py, scan_generated_skill.py)

The archive is reproducible: entries are sorted and carry a fixed timestamp,
so the same checkout always produces byte-identical output.

Usage:
    python3 tools/build_plugin.py                  # -> dist/book-to-skill.plugin
    python3 tools/build_plugin.py -o out.zip
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_NAME = "book-to-skill"
SKILL_PREFIX = f"skills/{PLUGIN_NAME}"
# 1980-01-01 is the earliest timestamp a zip entry can carry.
FIXED_DATE = (1980, 1, 1, 0, 0, 0)

# Files copied into the skill directory, relative to the repository root.
SKILL_FILES = (
    "SKILL.md",
    "LICENSE.md",
    "scripts/extract.py",
    "tools/validate_skill.py",
    "tools/scan_generated_skill.py",
)
PACKAGE_DIR = "book_to_skill"


def project_version(pyproject: Path = ROOT / "pyproject.toml") -> str:
    match = re.search(
        r'^version\s*=\s*"([^"]+)"', pyproject.read_text(encoding="utf-8"), re.M
    )
    if not match:
        raise SystemExit(f"could not read version from {pyproject}")
    return match.group(1)


def manifest(version: str) -> dict:
    return {
        "name": PLUGIN_NAME,
        "version": version,
        "description": (
            "Convert books and documents (PDF, EPUB, DOCX, HTML, Markdown, "
            "text, RTF) into structured, on-demand agent skills."
        ),
        "author": {"name": "book-to-skill contributors"},
        "homepage": "https://github.com/virgiliojr94/book-to-skill",
        "repository": "https://github.com/virgiliojr94/book-to-skill",
        "license": "MIT",
        "keywords": ["books", "documents", "skills", "pdf", "epub", "knowledge"],
    }


def plugin_readme(version: str) -> str:
    return f"""# book-to-skill (Claude plugin) v{version}

Turns a book or document into a structured, on-demand agent skill:
core frameworks in a small `SKILL.md`, chapters loaded only when asked.

## Use

Ask Claude to convert a document, or run the skill directly:

    /book-to-skill <path|folder|glob> [skill-name]

## Requirements

- `python3` (3.9+) on the machine running the skill. Plain text, Markdown,
  HTML, EPUB and DOCX work with the standard library alone.
- Optional extractors improve quality (e.g. `pip install pypdf` for PDFs).
  The skill offers to install what is missing; run
  `python3 skills/book-to-skill/scripts/extract.py --check` for a report.

Full documentation: https://github.com/virgiliojr94/book-to-skill
"""


def collect(root: Path = ROOT) -> dict[str, bytes]:
    """Map archive path -> file bytes for every file in the plugin."""
    version = project_version(root / "pyproject.toml")
    entries: dict[str, bytes] = {
        ".claude-plugin/plugin.json": (
            json.dumps(manifest(version), indent=2) + "\n"
        ).encode("utf-8"),
        "README.md": plugin_readme(version).encode("utf-8"),
        "LICENSE.md": (root / "LICENSE.md").read_bytes(),
    }
    for rel in SKILL_FILES:
        entries[f"{SKILL_PREFIX}/{rel}"] = (root / rel).read_bytes()
    for path in sorted((root / PACKAGE_DIR).rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        rel = path.relative_to(root).as_posix()
        entries[f"{SKILL_PREFIX}/{rel}"] = path.read_bytes()
    return entries


def build(output: Path, root: Path = ROOT) -> list[str]:
    entries = collect(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    names = sorted(entries)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in names:
            info = zipfile.ZipInfo(name, date_time=FIXED_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            executable = name.endswith("scripts/extract.py") or name.startswith(
                f"{SKILL_PREFIX}/tools/"
            )
            info.external_attr = (0o755 if executable else 0o644) << 16
            archive.writestr(info, entries[name])
    return names


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=ROOT / "dist" / f"{PLUGIN_NAME}.plugin",
        help="archive to write (default: dist/book-to-skill.plugin)",
    )
    args = parser.parse_args(argv)
    names = build(args.output)
    print(f"Wrote {args.output} ({len(names)} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
