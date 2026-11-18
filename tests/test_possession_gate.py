"""Possession-confirmation gate contract in the converter spec (Step 0.5)."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SKILL_MD = ROOT / "SKILL.md"


@pytest.fixture(scope="module")
def skill():
    if not SKILL_MD.exists():
        pytest.skip("SKILL.md not present (e.g. installed sdist)")
    return SKILL_MD.read_text(encoding="utf-8")


def _gate(skill):
    return skill[skill.index("## Step 0.5"):skill.index("## Step 1 ")]


def test_gate_exists_before_extraction(skill):
    assert "## Step 0.5 — Possession confirmation (mandatory)" in skill
    assert skill.index("## Step 0.5") < skill.index("## Step 1 ") < skill.index("## Step 2 ")


def test_gate_asks_for_physical_or_digital_copy_in_possession(skill):
    gate = _gate(skill)
    assert "physical or digital" in gate
    assert "in your possession right now" in gate
    assert "copyrighted" in gate


def test_gate_stops_without_confirmation(skill):
    gate = _gate(skill)
    assert "STOP without extracting" in gate
    assert "Do not pick this option on the user's behalf" in gate
    assert "No flag, environment variable" in gate


def test_fold_in_mode_runs_the_gate(skill):
    mode4 = skill[skill.index("### 4. Update / Fold-in"):skill.index("## Skill Locations")]
    assert "Step 0.5 (possession confirmation)" in mode4
