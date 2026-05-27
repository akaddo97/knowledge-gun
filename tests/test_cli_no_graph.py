"""Tests for the CLI ``--no-graph`` flag and its ``_intro_only_bundle`` helper.

Lives in its own file so the existing ``test_bundle_generator.py`` suite
(BFS walker + renderer + topic loader + CLI core + demo assertions) stays
focused on the bundle generator itself.
"""
from __future__ import annotations

from knowledge_gun.cli import _intro_only_bundle, main


def test_intro_only_bundle_has_intro_only_header():
    out = _intro_only_bundle("studio")
    assert out.startswith("# Studio — context bundle (intro only)")
    assert "## Static brief" in out


def test_intro_only_bundle_skips_graph_sections():
    out = _intro_only_bundle("studio")
    assert "Graph neighbourhood" not in out
    assert "How to use this bundle" not in out


def test_intro_only_bundle_includes_intro_body():
    out = _intro_only_bundle("studio")
    assert "Lantern-Bough Games" in out


def test_intro_only_bundle_unknown_topic_returns_fallback():
    out = _intro_only_bundle("nonexistent_topic_xyz")
    assert out.startswith("# Topic not found: nonexistent_topic_xyz")
    assert "Available topics:" in out


def test_main_no_graph_flag_dispatches_to_intro_only(capsys):
    rc = main(["--topic", "studio", "--no-graph"])
    assert rc == 0
    captured = capsys.readouterr()
    assert captured.out.startswith("# Studio — context bundle (intro only)")
    assert "Graph neighbourhood" not in captured.out


def test_main_default_path_still_includes_graph(capsys):
    rc = main(["--topic", "studio"])
    assert rc == 0
    captured = capsys.readouterr()
    assert "Graph neighbourhood" in captured.out
