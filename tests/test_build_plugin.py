"""Contract for the Claude plugin package produced by tools/build_plugin.py."""

import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import build_plugin  # noqa: E402

SKILL_DIR = "skills/book-to-skill"


@pytest.fixture
def plugin(tmp_path):
    out = tmp_path / "book-to-skill.plugin"
    build_plugin.build(out)
    return out


def test_manifest_is_valid_and_versioned(plugin):
    with zipfile.ZipFile(plugin) as archive:
        data = json.loads(archive.read(".claude-plugin/plugin.json"))
    assert data["name"] == "book-to-skill"
    assert data["version"] == build_plugin.project_version()


def test_skill_ships_with_its_extractor_and_tools(plugin):
    with zipfile.ZipFile(plugin) as archive:
        names = set(archive.namelist())
        assert archive.read(f"{SKILL_DIR}/SKILL.md") == (ROOT / "SKILL.md").read_bytes()
    for required in (
        f"{SKILL_DIR}/scripts/extract.py",
        f"{SKILL_DIR}/book_to_skill/cli.py",
        f"{SKILL_DIR}/book_to_skill/parsers/pdf.py",
        f"{SKILL_DIR}/tools/scan_generated_skill.py",
        f"{SKILL_DIR}/tools/validate_skill.py",
    ):
        assert required in names
    assert not [n for n in names if "__pycache__" in n or n.endswith(".pyc")]


def test_build_is_reproducible(tmp_path):
    a, b = tmp_path / "a.plugin", tmp_path / "b.plugin"
    build_plugin.build(a)
    build_plugin.build(b)
    assert a.read_bytes() == b.read_bytes()


def test_unpacked_plugin_extractor_runs(plugin, tmp_path):
    dest = tmp_path / "installed"
    with zipfile.ZipFile(plugin) as archive:
        archive.extractall(dest)
    sample = tmp_path / "sample.md"
    sample.write_text("# Chapter 1\n\nA synthetic sentence.\n", encoding="utf-8")
    env = os.environ.copy()
    env["BOOK_SKILL_WORKDIR"] = str(tmp_path / "work")
    result = subprocess.run(
        [sys.executable, str(dest / SKILL_DIR / "scripts" / "extract.py"), str(sample)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "work" / "full_text.txt").is_file()


def test_probe_prefers_claude_skill_dir(tmp_path):
    """SKILL.md's extractor probe finds the plugin copy via CLAUDE_SKILL_DIR."""
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    start = skill.index('SCRIPT_PATH=""')
    end = skill.index('\nif [ -z "$SCRIPT_PATH" ]', start)
    script = skill[start:end] + '\nprintf "%s" "$SCRIPT_PATH"\n'

    home = tmp_path / "home"
    shared = home / ".agents/skills/book-to-skill/scripts/extract.py"
    plugin_copy = tmp_path / "plugin" / SKILL_DIR / "scripts/extract.py"
    for path in (shared, plugin_copy):
        path.parent.mkdir(parents=True)
        path.touch()

    env = os.environ.copy()
    env.pop("HERMES_AGENT", None)
    env["HOME"] = str(home)
    env["CLAUDE_SKILL_DIR"] = str(plugin_copy.parent.parent)
    try:
        found = subprocess.run(
            ["bash", "-c", script], cwd=tmp_path, env=env,
            capture_output=True, text=True, check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        pytest.skip(f"bash unavailable: {exc}")
    assert Path(found).resolve() == plugin_copy.resolve()

    env.pop("CLAUDE_SKILL_DIR")
    found = subprocess.run(
        ["bash", "-c", script], cwd=tmp_path, env=env,
        capture_output=True, text=True, check=True,
    ).stdout
    assert Path(found).resolve() == shared.resolve()
