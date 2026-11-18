"""Claude plugin marketplace contract: manifests and plugin-install extractor discovery."""

import json
import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parent.parent
SKILL = (ROOT / "SKILL.md").read_text(encoding="utf-8")
PLUGIN_DIR = ROOT / ".claude-plugin"


def _extract_probe_script(skill_text=SKILL):
    start = skill_text.index('SCRIPT_PATH=""')
    end = skill_text.index('\nif [ -z "$SCRIPT_PATH" ]', start)
    return skill_text[start:end] + '\nprintf "%s" "$SCRIPT_PATH"\n'


def _run_probe(script, home, cwd):
    env = os.environ.copy()
    env["HOME"] = str(home)
    env.pop("HERMES_AGENT", None)
    env.pop("CLAUDE_SKILL_DIR", None)
    return subprocess.run(
        ["bash", "-c", script], cwd=cwd, env=env, check=True, capture_output=True, text=True
    ).stdout


def test_marketplace_lists_the_repo_root_plugin():
    marketplace = json.loads((PLUGIN_DIR / "marketplace.json").read_text(encoding="utf-8"))
    plugins = {entry["name"]: entry for entry in marketplace["plugins"]}
    assert plugins["book-to-skill"]["source"] == "./"


def test_plugin_manifest_ships_root_skill_without_pinned_version():
    plugin = json.loads((PLUGIN_DIR / "plugin.json").read_text(encoding="utf-8"))
    assert plugin["name"] == "book-to-skill"
    assert plugin["skills"] == ["./"]
    # No pinned version: Claude falls back to the git commit, so the manifest
    # cannot drift from pyproject.toml between releases.
    assert "version" not in plugin


def test_probe_finds_extractor_in_plugin_cache(tmp_path):
    home = tmp_path / "home"
    extractor = (
        home / ".claude" / "plugins" / "cache" / "book-to-skill" / "book-to-skill"
        / "abc123" / "scripts" / "extract.py"
    )
    extractor.parent.mkdir(parents=True)
    extractor.touch()
    cwd = tmp_path / "work"
    cwd.mkdir()
    assert Path(_run_probe(_extract_probe_script(), home, cwd)) == extractor


def test_substituted_skill_dir_takes_precedence(tmp_path):
    home = tmp_path / "home"
    personal = home / ".agents" / "skills" / "book-to-skill" / "scripts" / "extract.py"
    personal.parent.mkdir(parents=True)
    personal.touch()
    plugin_root = tmp_path / "installed-plugin"
    extractor = plugin_root / "scripts" / "extract.py"
    extractor.parent.mkdir(parents=True)
    extractor.touch()
    cwd = tmp_path / "work"
    cwd.mkdir()
    # Claude replaces ${CLAUDE_SKILL_DIR} in the skill body before the agent runs it.
    script = _extract_probe_script(SKILL.replace("${CLAUDE_SKILL_DIR}", str(plugin_root)))
    assert Path(_run_probe(script, home, cwd)) == extractor


def test_unsubstituted_skill_dir_falls_through_on_other_hosts(tmp_path):
    home = tmp_path / "home"
    personal = home / ".agents" / "skills" / "book-to-skill" / "scripts" / "extract.py"
    personal.parent.mkdir(parents=True)
    personal.touch()
    cwd = tmp_path / "work"
    cwd.mkdir()
    assert Path(_run_probe(_extract_probe_script(), home, cwd)) == personal
