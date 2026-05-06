"""Knowledge Gun — paste-ready chatbot context bundles from a curated graph.

Emits a single-message context bundle to drop into the opening turn of a fresh
LLM chat. One bundle per topic. Each bundle = a curated static intro
(``intros/<topic>.intro.md``) + a dynamic graph-neighbourhood snapshot (BFS
walk from anchor nodes listed in ``roots/<topic>.roots.json``).

Public surface:
    AVAILABLE_TOPICS              — topic strings derived from the intros dir
    load_intro(topic)             — read intro markdown (None if missing)
    load_roots(topic)             — read roots.json (empty list if missing)
    graph_neighbourhood(roots, …) — BFS walker, capped at NEIGHBOURHOOD_NODE_CAP
    render_neighbourhood_md(nb)   — format neighbourhood as readable markdown
    generate_bundle(topic)        — full assembled bundle (never raises)

Defaults point at the bundled demo graph under ``examples/demo_graph/``. Override
via env vars: ``KNOWLEDGE_GUN_GRAPH_PATH``, ``KNOWLEDGE_GUN_INTRO_DIR``,
``KNOWLEDGE_GUN_ROOTS_DIR``. Tests can also patch the module-level paths.

The generator is a read-only consumer of the graph file. No caching — bundles
regenerate on every request.
"""
from __future__ import annotations

import json
import os
from collections import deque
from pathlib import Path
from typing import Iterable

__version__ = "0.1.0"

# Repo root: src/knowledge_gun/__init__.py → up two = repo root.
_REPO_ROOT = Path(__file__).resolve().parents[2]

GRAPH_PATH = Path(
    os.environ.get(
        "KNOWLEDGE_GUN_GRAPH_PATH",
        _REPO_ROOT / "examples" / "demo_graph" / "graph.json",
    )
)
BUNDLE_DIR = Path(
    os.environ.get(
        "KNOWLEDGE_GUN_INTRO_DIR",
        _REPO_ROOT / "examples" / "demo_graph" / "intros",
    )
)
ROOTS_DIR = Path(
    os.environ.get(
        "KNOWLEDGE_GUN_ROOTS_DIR",
        _REPO_ROOT / "examples" / "demo_graph" / "roots",
    )
)

NEIGHBOURHOOD_NODE_CAP = 80
DEFAULT_DEPTH = 2
WORD_CAP = 4000

_NODE_TYPE_ORDER = (
    "person",
    "company",
    "institution",
    "programme",
    "job_posting",
    "role_type",
    "skill",
    "concept",
    "decision",
    "project",
    "conversation",
    "document",
    "city",
)

_NODE_TYPE_HEADERS = {
    "person":       "People",
    "company":      "Companies",
    "institution":  "Institutions",
    "programme":    "Programmes",
    "job_posting":  "Job postings",
    "role_type":    "Role types",
    "skill":        "Skills",
    "concept":      "Concepts",
    "decision":     "Decisions",
    "project":      "Projects",
    "conversation": "Recent conversations",
    "document":     "Source documents",
    "city":         "Cities",
}


def _available_topics() -> list[str]:
    """Topics derived from filesystem — ``<topic>.intro.md`` files in BUNDLE_DIR."""
    if not BUNDLE_DIR.exists():
        return []
    return sorted(
        p.stem.removesuffix(".intro")
        for p in BUNDLE_DIR.glob("*.intro.md")
    )


def __getattr__(name: str):
    if name == "AVAILABLE_TOPICS":
        return _available_topics()
    raise AttributeError(name)


def load_intro(topic: str) -> str | None:
    """Read ``<topic>.intro.md``. None if missing."""
    path = BUNDLE_DIR / f"{topic}.intro.md"
    if not path.exists():
        return None
    return path.read_text().strip()


def load_roots(topic: str) -> list[str]:
    """Read ``<topic>.roots.json`` — list of seed node ids. Empty list if missing
    or malformed."""
    path = ROOTS_DIR / f"{topic}.roots.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [str(x) for x in data]


def _load_graph() -> dict:
    if not GRAPH_PATH.exists():
        return {"nodes": [], "edges": []}
    try:
        data = json.loads(GRAPH_PATH.read_text())
    except json.JSONDecodeError:
        return {"nodes": [], "edges": []}
    if "edges" not in data:
        data["edges"] = data.get("links", [])
    return data


def graph_neighbourhood(
    root_ids: Iterable[str],
    depth: int = DEFAULT_DEPTH,
    graph: dict | None = None,
) -> dict:
    """BFS walk from ``root_ids`` up to ``depth`` hops, capped at
    NEIGHBOURHOOD_NODE_CAP nodes. Returns ``{"nodes": [...], "edges": [...]}``
    containing visited nodes and edges between them.
    """
    roots = [r for r in root_ids if r]
    if not roots:
        return {"nodes": [], "edges": []}

    g = graph if graph is not None else _load_graph()
    nodes_by_id = {n["id"]: n for n in g.get("nodes", [])}
    edges = g.get("edges", g.get("links", []))

    adj: dict[str, list[tuple[str, int]]] = {}
    for idx, e in enumerate(edges):
        s, t = e.get("source"), e.get("target")
        if not s or not t:
            continue
        adj.setdefault(s, []).append((t, idx))
        adj.setdefault(t, []).append((s, idx))

    visited: set[str] = set()
    queue: deque[tuple[str, int]] = deque()
    for r in roots:
        if r in nodes_by_id and r not in visited:
            visited.add(r)
            queue.append((r, 0))

    while queue and len(visited) < NEIGHBOURHOOD_NODE_CAP:
        node_id, dist = queue.popleft()
        if dist >= depth:
            continue
        for neighbour_id, _ in adj.get(node_id, []):
            if neighbour_id in visited:
                continue
            if neighbour_id not in nodes_by_id:
                continue
            visited.add(neighbour_id)
            queue.append((neighbour_id, dist + 1))
            if len(visited) >= NEIGHBOURHOOD_NODE_CAP:
                break

    out_nodes = [nodes_by_id[i] for i in visited if i in nodes_by_id]
    out_edges = [
        e for e in edges
        if e.get("source") in visited and e.get("target") in visited
    ]
    return {"nodes": out_nodes, "edges": out_edges}


def _node_summary(node: dict) -> str:
    """Compact one-liner appended after ``<label> (<id>)``. Empty string if none."""
    for field in ("headline", "current_title", "description", "about"):
        v = node.get(field)
        if isinstance(v, str) and v.strip():
            text = v.strip().replace("\n", " ")
            return text if len(text) <= 140 else text[:137] + "…"
    aliases = node.get("aliases")
    if isinstance(aliases, list) and aliases:
        return f"aka {aliases[0]}"
    return ""


def render_neighbourhood_md(neighbourhood: dict) -> str:
    """Format neighbourhood as readable markdown grouped by file_type. Includes
    a recent-activity section listing provisional nodes with timestamps."""
    nodes = neighbourhood.get("nodes", [])
    edges = neighbourhood.get("edges", [])
    if not nodes:
        return "_No graph neighbourhood available for this topic._\n"

    by_type: dict[str, list[dict]] = {}
    for n in nodes:
        ftype = n.get("file_type", "unknown")
        by_type.setdefault(ftype, []).append(n)

    out: list[str] = []
    out.append(f"_Graph snapshot: {len(nodes)} nodes, {len(edges)} edges in scope._\n")

    seen_types: set[str] = set()
    for ftype in _NODE_TYPE_ORDER:
        group = by_type.get(ftype)
        if not group:
            continue
        seen_types.add(ftype)
        header = _NODE_TYPE_HEADERS.get(ftype, ftype.title())
        out.append(f"\n### {header}")
        for n in sorted(group, key=lambda x: x.get("label", x.get("id", ""))):
            label = n.get("label", n.get("id", "?"))
            nid = n.get("id", "?")
            summary = _node_summary(n)
            line = f"- {label} ({nid})"
            if summary:
                line += f" — {summary}"
            out.append(line)

    leftover_types = sorted(set(by_type) - seen_types)
    for ftype in leftover_types:
        out.append(f"\n### {ftype.title()}")
        for n in sorted(by_type[ftype], key=lambda x: x.get("label", x.get("id", ""))):
            label = n.get("label", n.get("id", "?"))
            nid = n.get("id", "?")
            summary = _node_summary(n)
            line = f"- {label} ({nid})"
            if summary:
                line += f" — {summary}"
            out.append(line)

    provisional = [
        n for n in nodes
        if n.get("verified") is False and n.get("provisional_added_at")
    ]
    if provisional:
        out.append("\n### Recent activity (provisional, awaiting verify)")
        for n in sorted(provisional, key=lambda x: x.get("provisional_added_at", ""), reverse=True):
            ts = n.get("provisional_added_at", "?")
            label = n.get("label", n.get("id", "?"))
            nid = n.get("id", "?")
            out.append(f"- {ts} — {label} ({nid})")

    return "\n".join(out) + "\n"


def _topic_title(topic: str) -> str:
    return topic.replace("_", " ").title()


def _framing_header(topic: str) -> str:
    title = _topic_title(topic)
    return (
        f"# {title} — context bundle\n\n"
        "> Paste this as the opening message of a fresh chat. Everything below\n"
        "> is what the chatbot needs to know to be useful on this topic.\n"
        "> Treat it as orientation, not a script.\n"
    )


def _footer(topic: str) -> str:
    available = _available_topics()
    others = [t for t in available if t != topic]
    other_lenses = ", ".join(others) if others else "(none configured)"
    return (
        "\n---\n\n"
        "## How to use this bundle\n\n"
        "Read it once, then reply at the level of detail it implies. Push back\n"
        "when the user is being generic; ask one clarifying question rather than\n"
        f"guessing when context is missing. This bundle is the {_topic_title(topic).lower()} "
        "lens on the underlying knowledge graph. "
        f"Other lenses available: {other_lenses}.\n"
    )


def _unknown_topic_fallback(topic: str) -> str:
    available = _available_topics()
    if available:
        avail_str = ", ".join(available)
        return (
            f"# Topic not found: {topic}\n\n"
            f"No intro file at ``{BUNDLE_DIR}/{topic}.intro.md``.\n\n"
            f"Available topics: {avail_str}.\n"
        )
    return (
        f"# Topic not found: {topic}\n\n"
        f"No bundle topics are configured yet — drop intro files at "
        f"``{BUNDLE_DIR}/<topic>.intro.md``.\n"
    )


def generate_bundle(topic: str) -> str:
    """Assemble: framing header + static intro + dynamic graph snapshot + footer.

    Never raises. Returns a friendly fallback string when the topic is unknown
    or the intro file is missing.
    """
    try:
        intro = load_intro(topic)
        if intro is None:
            return _unknown_topic_fallback(topic)

        roots = load_roots(topic)
        graph = _load_graph()
        neighbourhood = graph_neighbourhood(roots, depth=DEFAULT_DEPTH, graph=graph)
        nb_md = render_neighbourhood_md(neighbourhood)

        parts = [
            _framing_header(topic),
            "\n## Static brief\n\n",
            intro.rstrip() + "\n",
            "\n---\n\n",
            f"## Graph neighbourhood (depth={DEFAULT_DEPTH}, capped at {NEIGHBOURHOOD_NODE_CAP} nodes)\n\n",
            nb_md,
            _footer(topic),
        ]
        return "".join(parts)
    except Exception as exc:  # pragma: no cover
        return (
            f"# Bundle generator error: {topic}\n\n"
            f"Unexpected failure assembling the bundle: {exc!r}.\n"
            "Available topics: " + ", ".join(_available_topics()) + ".\n"
        )


__all__ = [
    "AVAILABLE_TOPICS",
    "BUNDLE_DIR",
    "ROOTS_DIR",
    "GRAPH_PATH",
    "NEIGHBOURHOOD_NODE_CAP",
    "DEFAULT_DEPTH",
    "WORD_CAP",
    "load_intro",
    "load_roots",
    "graph_neighbourhood",
    "render_neighbourhood_md",
    "generate_bundle",
]
