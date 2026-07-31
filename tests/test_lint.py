"""Catch undefined names before Rhino does.

A command's body only runs inside Rhino, so a missing import survives every
headless test, every `compileall`, and every import-only check — and then throws
`NameError` halfway through a command, after the user has already answered
prompts. That is exactly how `bc_name` reached a Rhino run on 2026-07-30.

Ruff's F821 finds them statically. Skipped when ruff is not installed, so this
never blocks a run that simply lacks the dev tooling.
"""

import pathlib
import shutil
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]

ruff = shutil.which("ruff")
pytestmark = pytest.mark.skipif(ruff is None, reason="ruff not installed")


@pytest.mark.parametrize("target", ["commands", "src", "tests"])
def test_no_undefined_names(target):
    """F821 — a name used but never defined or imported."""
    result = subprocess.run(
        [ruff, "check", "--select", "F821", "--output-format", "concise", target],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"undefined names in {target}/:\n{result.stdout}"


@pytest.mark.parametrize("target", ["commands", "src", "tests"])
def test_no_redefinitions(target):
    """F811 — a second definition silently shadowing the first."""
    result = subprocess.run(
        [ruff, "check", "--select", "F811", "--output-format", "concise", target],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"redefinitions in {target}/:\n{result.stdout}"
