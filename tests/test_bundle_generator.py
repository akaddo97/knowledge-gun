"""Knowledge Gun — bundle generator tests.

Covers (adapted from the original 25-test suite, Flask web-surface tests dropped
since this package ships CLI-only):
  - generate_bundle(<topic>) returns a non-empty string with framing + intro markers.
  - generate_bundle("nonexistent") returns a friendly fallback (no raise, mentions
    available topics).
  - graph_neighbourhood walks 2 hops, dedupes, and respects the 80-node cap.
  - graph_neighbourhood([]) returns clean empty result.
  - render_neighbourhood_md groups by file_type and tolerates missing fields.
  - CLI exits 0 with bundle on stdout for known topic.
  - CLI exits non-zero (argparse rejection) for unknown topic.
  - All four intro files exist and are non-empty.
  - Each topic's bundle stays under the 4,000-word cap.
  - Demo-specific: studio bundle contains the founder's name; team bundle lists
    all six team members; projects bundle mentions all three projects.

HOW TO RUN
  pytest tests/ -v
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import knowledge_gun as bg  # noqa: E402


TOPICS = ["studio", "team", "projects", "industry"]


# ── module-level helpers ──────────────────────────────────────────────────────

def test_available_topics_includes_all_four():
    """Filesystem-derived topic list must include the four canonical demo topics."""
    available = bg.AVAILABLE_TOPICS
    for t in TOPICS:
        assert t in available, f"missing topic: {t}"


def test_intro_files_exist_and_nonempty():
    """All four intro files must exist with real content — regression guard
    against an agent leaving placeholders."""
    for t in TOPICS:
        p = bg.BUNDLE_DIR / f"{t}.intro.md"
        assert p.exists(), f"missing intro file: {p}"
        body = p.read_text().strip()
        assert len(body) > 200, f"intro too short for {t}: {len(body)} chars"


def test_load_intro_returns_none_for_unknown():
    assert bg.load_intro("definitely_not_a_topic_42") is None


def test_load_roots_returns_empty_for_unknown():
    assert bg.load_roots("definitely_not_a_topic_42") == []


# ── graph_neighbourhood ───────────────────────────────────────────────────────

_FAKE_GRAPH = {
    "nodes": [
        {"id": "a", "label": "A", "file_type": "person"},
        {"id": "b", "label": "B", "file_type": "person"},
        {"id": "c", "label": "C", "file_type": "company"},
        {"id": "d", "label": "D", "file_type": "skill"},
        {"id": "e", "label": "E", "file_type": "concept"},
    ],
    "edges": [
        {"source": "a", "target": "b", "relation": "knows"},
        {"source": "b", "target": "c", "relation": "works_at"},
        {"source": "c", "target": "d", "relation": "uses"},
        {"source": "d", "target": "e", "relation": "relates_to"},
    ],
}


def test_neighbourhood_empty_roots_returns_empty():
    """Empty root list → empty result, no errors."""
    nb = bg.graph_neighbourhood([], depth=2, graph=_FAKE_GRAPH)
    assert nb == {"nodes": [], "edges": []}


def test_neighbourhood_walks_two_hops_no_duplicates():
    """From 'a' at depth=2 should reach a, b, c — but not d (3 hops) or e (4)."""
    nb = bg.graph_neighbourhood(["a"], depth=2, graph=_FAKE_GRAPH)
    ids = {n["id"] for n in nb["nodes"]}
    assert ids == {"a", "b", "c"}, f"unexpected node set: {ids}"
    assert len(nb["nodes"]) == len(ids), "duplicate nodes returned"
    edge_pairs = {(e["source"], e["target"]) for e in nb["edges"]}
    assert ("a", "b") in edge_pairs
    assert ("b", "c") in edge_pairs
    assert ("d", "e") not in edge_pairs


def test_neighbourhood_respects_node_cap():
    """A dense star graph → cap at NEIGHBOURHOOD_NODE_CAP nodes."""
    star_nodes = [{"id": "hub", "label": "Hub", "file_type": "person"}]
    star_edges = []
    for i in range(200):
        nid = f"leaf_{i}"
        star_nodes.append({"id": nid, "label": f"L{i}", "file_type": "person"})
        star_edges.append({"source": "hub", "target": nid, "relation": "knows"})
    star_graph = {"nodes": star_nodes, "edges": star_edges}

    nb = bg.graph_neighbourhood(["hub"], depth=2, graph=star_graph)
    assert len(nb["nodes"]) <= bg.NEIGHBOURHOOD_NODE_CAP
    assert len(nb["nodes"]) == bg.NEIGHBOURHOOD_NODE_CAP, (
        f"expected to saturate cap, got {len(nb['nodes'])}"
    )


def test_neighbourhood_skips_missing_root_ids():
    """Roots that don't exist in the graph must be silently dropped."""
    nb = bg.graph_neighbourhood(["a", "ghost_node"], depth=1, graph=_FAKE_GRAPH)
    ids = {n["id"] for n in nb["nodes"]}
    assert "ghost_node" not in ids
    assert "a" in ids


# ── render_neighbourhood_md ──────────────────────────────────────────────────

def test_render_groups_by_file_type():
    """Render must produce a section header per file_type present."""
    md = bg.render_neighbourhood_md({
        "nodes": _FAKE_GRAPH["nodes"],
        "edges": _FAKE_GRAPH["edges"],
    })
    assert "### People" in md
    assert "### Companies" in md
    assert "### Skills" in md
    assert "### Concepts" in md
    assert "A (a)" in md
    assert "B (b)" in md


def test_render_handles_missing_fields():
    """Nodes missing label, file_type, etc. shouldn't crash."""
    nodes = [
        {"id": "x"},
        {"id": "y", "label": "Y"},
        {"id": "z", "label": "Z", "file_type": "weird_type"},
    ]
    md = bg.render_neighbourhood_md({"nodes": nodes, "edges": []})
    assert "x" in md
    assert "Y (y)" in md
    assert "Z (z)" in md


def test_render_empty_returns_friendly_message():
    md = bg.render_neighbourhood_md({"nodes": [], "edges": []})
    assert "No graph neighbourhood" in md


# ── generate_bundle ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("topic", TOPICS)
def test_generate_bundle_topic_returns_content(topic):
    """Each canonical topic returns a non-empty bundle with framing + intro."""
    md = bg.generate_bundle(topic)
    assert isinstance(md, str)
    assert len(md) > 1000, f"{topic} bundle suspiciously short: {len(md)} chars"
    assert "# " in md, "framing header missing"
    assert "Static brief" in md, "intro section header missing"
    assert "Graph neighbourhood" in md, "graph section header missing"
    assert "How to use this bundle" in md, "footer missing"


def test_generate_bundle_unknown_topic_friendly_fallback():
    """Unknown topic → friendly fallback string mentioning available topics."""
    md = bg.generate_bundle("definitely_not_a_topic_42")
    assert isinstance(md, str)
    assert len(md) > 0
    assert "not found" in md.lower() or "unknown" in md.lower()
    assert any(t in md for t in TOPICS)


@pytest.mark.parametrize("topic", TOPICS)
def test_bundle_stays_under_word_cap(topic):
    """Bundle must stay under 4,000 words on the demo graph snapshot."""
    md = bg.generate_bundle(topic)
    words = len(md.split())
    assert words < bg.WORD_CAP, f"{topic} bundle too long: {words} > {bg.WORD_CAP}"


# ── demo-specific tests ──────────────────────────────────────────────────────

def test_studio_bundle_contains_founder_name():
    """The demo studio bundle must surface the founder — proves topic scoping
    pulls anchored people into the neighbourhood."""
    md = bg.generate_bundle("studio")
    assert "Maya Okonkwo" in md, "founder missing from studio bundle"
    assert "person_maya_okonkwo" in md, "founder id missing from graph snapshot"


def test_team_bundle_lists_all_six_team_members():
    """The team bundle's graph neighbourhood must include all six people."""
    md = bg.generate_bundle("team")
    expected_names = [
        "Maya Okonkwo",
        "Jonas Lindqvist",
        "Priya Balasubramanian",
        "Diego Alvarez",
        "Sarah Chen",
        "Amir Hassan",
    ]
    missing = [n for n in expected_names if n not in md]
    assert not missing, f"team members missing from team bundle: {missing}"


def test_projects_bundle_mentions_all_three_projects():
    """The projects bundle must surface all three game projects."""
    md = bg.generate_bundle("projects")
    expected_projects = [
        "Paper Lanterns",
        "Tide Études",
        "Cinder Path",
    ]
    missing = [p for p in expected_projects if p not in md]
    assert not missing, f"projects missing from projects bundle: {missing}"


# ── CLI surface ───────────────────────────────────────────────────────────────

CLI_PATH = ROOT / "src" / "knowledge_gun" / "cli.py"


def test_cli_topic_studio_writes_bundle_to_stdout():
    """python -m knowledge_gun.cli --topic studio → exit 0 + bundle on stdout."""
    proc = subprocess.run(
        [sys.executable, "-m", "knowledge_gun.cli", "--topic", "studio"],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(ROOT),
        env={**__import__("os").environ, "PYTHONPATH": str(ROOT / "src")},
    )
    assert proc.returncode == 0, f"non-zero exit: stderr={proc.stderr}"
    assert "Studio — context bundle" in proc.stdout
    assert len(proc.stdout.split()) > 200


def test_cli_invalid_topic_exits_nonzero():
    """argparse must reject an unknown topic without our generator running."""
    proc = subprocess.run(
        [sys.executable, "-m", "knowledge_gun.cli", "--topic", "definitely_not_real"],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(ROOT),
        env={**__import__("os").environ, "PYTHONPATH": str(ROOT / "src")},
    )
    assert proc.returncode != 0
    assert "definitely_not_real" in proc.stderr or "invalid choice" in proc.stderr.lower()
