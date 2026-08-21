"""Test bootstrap for the agent-drift-guard Hermes plugin.

The plugin lives under ``hermes_plugin/agent-drift-guard/`` — a hyphenated
directory that Python cannot import with normal ``import`` syntax. Hermes'
plugin loader imports it by file path; we do the same here with
``importlib`` so the relative imports inside the package resolve exactly as
they do in production (and so no ``hermes`` core package is required to run
the unit tests — the plugin's own modules only depend on ``drift_guard``).

Exposes a ``agd`` fixture that returns the loaded plugin package module with a
fresh, isolated guard registry per test.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.resolve()

# drift_guard lives under src/; make it importable.
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

PLUGIN_DIR = ROOT / "hermes_plugin" / "agent-drift-guard"
PLUGIN_MODULE_NAME = "hermes_plugin_agent_drift_guard"


def load_plugin_package():
    """Load the hyphenated plugin package by path (mirrors Hermes loader)."""
    if PLUGIN_MODULE_NAME in sys.modules:
        return sys.modules[PLUGIN_MODULE_NAME]
    spec = importlib.util.spec_from_file_location(
        PLUGIN_MODULE_NAME,
        PLUGIN_DIR / "__init__.py",
        submodule_search_locations=[str(PLUGIN_DIR)],
    )
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = PLUGIN_MODULE_NAME
    sys.modules[PLUGIN_MODULE_NAME] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def agd():
    """Loaded plugin package with a fresh, per-test guard registry."""
    mod = load_plugin_package()
    from hermes_plugin_agent_drift_guard.session_guards import SessionGuards

    mod._guards = SessionGuards()
    yield mod
    mod._guards = SessionGuards()


# Load the plugin package at conftest import time so the test module can
# `from hermes_plugin_agent_drift_guard import ...` at top level.
load_plugin_package()
