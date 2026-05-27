# Changelog

All notable changes to this project follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- README badges row (tests / license / Python 3.11+).
- "Pair with `knowledge-gun-mcp`" README section linking the MCP wrapper sibling.
- Status line above Quickstart.
- `examples/example_studio_bundle.md` — captured `knowledge-gun --topic studio` output as a worked example.
- `CHANGELOG.md` (this file).
- `--no-graph` CLI flag — emit just the curated intro, skip the dynamic graph-neighbourhood snapshot.

### Changed

- Refreshed docstring paths + demo-graph node-count after the `0e26039` relocation (was `examples/demo_graph/`, now `src/knowledge_gun/demo_graph/`).

### Removed

- Empty top-level `docs/` placeholder folder.

## [0.1.0] - 2026-05-06

### Added

- Initial release. Topic-scoped graph-neighbourhood walker + curated-intro context bundle generator.
- Public API: `AVAILABLE_TOPICS`, `load_intro`, `load_roots`, `graph_neighbourhood`, `render_neighbourhood_md`, `generate_bundle`.
- CLI: `knowledge-gun --topic <topic>` with `--copy` (macOS `pbcopy`) and `--list` flags.
- Bring-your-own-graph via `KNOWLEDGE_GUN_GRAPH_PATH`, `KNOWLEDGE_GUN_INTRO_DIR`, `KNOWLEDGE_GUN_ROOTS_DIR` environment variables.
- Bundled demo graph (fictional Lantern-Bough Games indie studio) — 30 nodes, 51 edges, four topics (`studio`, `team`, `projects`, `industry`).
- Test suite (25 cases) covering the BFS walker, markdown renderer, topic loader, CLI, and demo-bundle assertions.
- CI matrix: Ubuntu + macOS × Python 3.11 / 3.12 / 3.13.
- MIT licence.
