# Knowledge Gun

Generate paste-ready chatbot context bundles from a curated knowledge graph. Run once, paste once, your assistant is briefed with perfect context (e.g. career, projects, network or domain expertise). No vector database. No embedding cost. Just markdown.

## What it is

A topic-scoped graph-neighbourhood walker plus hand-written intro files. Point Knowledge Gun at a JSON knowledge graph, give it a topic with three to six anchor node ids, and it walks the graph two hops out from those anchors, formats the result as readable markdown, and prepends a curated intro paragraph. The output is a single message you paste into the opening turn of a fresh chat.

## The problem

Every fresh chat with an LLM starts cold. If you have non-trivial context — a network of people, a portfolio of projects, a stack of decisions you've made over years — re-typing that context per chat costs five to fifteen minutes and arrives as fragments. The chatbot ends up with a partial mental model and asks the same calibration questions every conversation.

## The approach

A curated knowledge graph plus a hand-written intro per topic plus a list of anchor node ids per topic. Knowledge Gun does the rest:

1. Read the intro file for the topic.
2. Read the anchor node ids for the topic.
3. Walk the graph two hops from those anchors, capped at 80 nodes.
4. Group the visited nodes by `file_type` (people, companies, projects, skills, concepts, documents, …).
5. Render as markdown with a framing header and a usage footer.

The output is a single context bundle, typically two to four thousand words, ready to paste.

## Quickstart

Requires Python 3.11+. **macOS users** — if your `python3` on PATH is Homebrew Python 3.13 or 3.14, you may hit a `platform.mac_ver()` returned empty value error from `uv` or pip. The fix is to use Python 3.12 explicitly:

```bash
# macOS Homebrew (works around the Python 3.13/3.14 platform.mac_ver bug)
uv venv --python /opt/homebrew/opt/python@3.12/bin/python3.12 .venv

# Or any other system with a working Python 3.11+
python3 -m venv .venv

source .venv/bin/activate
pip install -e ".[dev]"

# Run against the bundled demo graph (a fictional indie game studio).
knowledge-gun --topic studio
knowledge-gun --topic team --copy        # copies to clipboard on macOS
knowledge-gun --list                     # show configured topics + paths
```

The demo graph ships with four topics: `studio`, `team`, `projects`, `industry`. Each produces a one- to two-thousand-word bundle.

### Install from GitHub (one-liner, no clone needed)

```bash
uv venv --python /opt/homebrew/opt/python@3.12/bin/python3.12 /tmp/kg-test \
  && uv pip install --python /tmp/kg-test/bin/python git+https://github.com/akaddo97/knowledge-gun \
  && /tmp/kg-test/bin/knowledge-gun --topic studio | head -30
# Cleanup: rm -rf /tmp/kg-test
```

## Bring your own graph

Knowledge Gun reads three things — a graph file, an intros directory, and a roots directory. Override the paths via environment variables:

```bash
export KNOWLEDGE_GUN_GRAPH_PATH=path/to/graph.json
export KNOWLEDGE_GUN_INTRO_DIR=path/to/intros/
export KNOWLEDGE_GUN_ROOTS_DIR=path/to/roots/
knowledge-gun --topic <your_topic>
```

### Graph format

JSON with `nodes` and `edges` keys (`links` is also accepted as a synonym for `edges`):

```json
{
  "directed": true,
  "nodes": [
    {"id": "person_alice", "label": "Alice", "file_type": "person", "headline": "..."},
    {"id": "company_acme", "label": "Acme Corp", "file_type": "company"}
  ],
  "edges": [
    {"source": "person_alice", "target": "company_acme", "relation": "works_at"}
  ]
}
```

Node `file_type` is the grouping key in the rendered output. The recognised types are `person`, `company`, `institution`, `programme`, `job_posting`, `role_type`, `skill`, `concept`, `decision`, `project`, `conversation`, `document`, `city`. Unknown types render under their own section title.

This shape is intentionally the same one used by `graphify` and similar curated-graph tooling, so any graph in that ecosystem is interoperable without adaptation.

### Intros directory

One markdown file per topic, named `<topic>.intro.md`. Hand-written prose — this is the bit Knowledge Gun cannot generate. Five hundred to a thousand words per intro is typical. The demo intros under `src/knowledge_gun/demo_graph/intros/` are reference templates.

### Roots directory

One JSON file per topic, named `<topic>.roots.json`. A flat array of node ids that anchor the BFS walk:

```json
[
  "person_alice",
  "project_flagship",
  "company_acme"
]
```

Three to six anchors per topic is the sweet spot. Fewer than three under-scopes the bundle; more than six saturates the 80-node cap and the walk degrades into a flat dump.

## Architecture

```
intros/<topic>.intro.md  ─┐
                          ├─→ generate_bundle(topic) ─→ markdown
roots/<topic>.roots.json ─┤
                          │
graph.json (nodes + edges)┘
```

The walker (`graph_neighbourhood`) is BFS, depth-bounded (default 2 hops), node-capped (default 80). The renderer (`render_neighbourhood_md`) groups by `file_type` and emits a stable section order. Both are pure functions over the loaded graph dict — easy to test, easy to reuse.

The full public API:

```python
from knowledge_gun import (
    AVAILABLE_TOPICS,
    load_intro,
    load_roots,
    graph_neighbourhood,
    render_neighbourhood_md,
    generate_bundle,
)

md = generate_bundle("studio")
```

## Why not vector RAG?

Vector RAG is the default reach for "give the LLM context". For curated personal knowledge graphs it's the wrong tool.

- **Curation is the moat.** A vector index works without curation, but it loses the structure you spent time building. Knowledge Gun assumes you've curated and rewards that work — your graph's edges, file_types and aliases all show up in the rendered output.
- **No embedding cost, no embedding drift.** The graph is plain JSON. Regenerating a bundle is a sub-second filesystem read.
- **Deterministic and inspectable.** The same graph + same topic = byte-identical bundle. You can read what's going into the LLM before you paste it.

The trade-off: Knowledge Gun is single-graph, single-topic per bundle, and topic anchors are hand-picked. If you want one chat to silently search across thousands of documents on demand, use vector RAG. If you want to brief a chat on a curated body of knowledge once at the top of the conversation, use Knowledge Gun.

## Limits

- Synchronous and uncached — fine for a graph of a few thousand nodes, slow above that.
- Single-graph per invocation. Multi-graph fan-in is on the roadmap.
- No incremental updates — every call rebuilds the bundle.
- The intros are the load-bearing artefact. A bad intro produces a bad bundle no matter how good the graph is.

## Demo graph

The bundled `src/knowledge_gun/demo_graph/` is a fully fictional indie game studio (Lantern-Bough Games — six people, three projects, made up for the demo). It exists to make the tool runnable from a fresh clone without any setup. Regenerate it with:

```bash
python src/knowledge_gun/demo_graph/generate.py
```

## Tests

```bash
pytest tests/ -v
```

Twenty-five tests covering the BFS walker, the markdown renderer, the topic loader, the CLI, and three demo-specific assertions that prove the bundled graph still produces the expected bundles.

## License

MIT.
