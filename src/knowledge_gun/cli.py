"""Knowledge Gun CLI — emit a context bundle for the given topic.

Usage:
    knowledge-gun --topic studio
    knowledge-gun --topic team --copy
    python -m knowledge_gun.cli --list

``--copy`` pipes the bundle to ``pbcopy`` on macOS; falls back to stdout
elsewhere. ``--list`` prints the configured topics and exits.

Bring your own graph + intros + roots:

    KNOWLEDGE_GUN_GRAPH_PATH=path/to/graph.json \\
    KNOWLEDGE_GUN_INTRO_DIR=path/to/intros/ \\
    KNOWLEDGE_GUN_ROOTS_DIR=path/to/roots/ \\
    knowledge-gun --topic <topic>
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys

from . import (
    AVAILABLE_TOPICS,
    BUNDLE_DIR,
    GRAPH_PATH,
    ROOTS_DIR,
    generate_bundle,
)


def _build_parser(topics: list[str]) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="knowledge-gun",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    if topics:
        parser.add_argument(
            "--topic",
            choices=topics,
            help="Bundle topic — one of: " + ", ".join(topics),
        )
    else:
        parser.add_argument(
            "--topic",
            help="Bundle topic. (No topics currently configured — see --list.)",
        )
    parser.add_argument(
        "--copy",
        action="store_true",
        help="Pipe to clipboard via pbcopy instead of stdout (macOS only).",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List configured topics and the resolved graph + intro paths, then exit.",
    )
    return parser


def _emit(md: str, topic: str, copy: bool) -> int:
    if copy:
        pbcopy = shutil.which("pbcopy")
        if not pbcopy:
            print(
                "[knowledge-gun] pbcopy not available — emitting to stdout instead",
                file=sys.stderr,
            )
            sys.stdout.write(md)
            return 1
        subprocess.run([pbcopy], input=md.encode(), check=True)
        print(
            f"[knowledge-gun] {topic}: {len(md):,} chars copied to clipboard",
            file=sys.stderr,
        )
        return 0
    sys.stdout.write(md)
    return 0


def main(argv: list[str] | None = None) -> int:
    topics = AVAILABLE_TOPICS
    parser = _build_parser(topics)
    args = parser.parse_args(argv)

    if args.list:
        print(f"Graph:  {GRAPH_PATH}")
        print(f"Intros: {BUNDLE_DIR}")
        print(f"Roots:  {ROOTS_DIR}")
        if topics:
            print("Topics: " + ", ".join(topics))
        else:
            print("Topics: (none configured)")
        return 0

    if not args.topic:
        parser.error("--topic is required (or use --list to see configured topics)")

    md = generate_bundle(args.topic)
    return _emit(md, args.topic, args.copy)


if __name__ == "__main__":
    sys.exit(main())
