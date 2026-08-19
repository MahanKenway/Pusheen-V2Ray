"""Small command-line interface for the initial Kaveh foundation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from kaveh.adapters.protocols.registry import ParserRegistry
from kaveh.application.commands.ingest_sources import IngestSources
from kaveh.config.source_registry import load_sources
from kaveh.infrastructure.http.http_source_client import BoundedHttpsSourceClient
from kaveh.infrastructure.persistence.in_memory import InMemoryConfigRepository


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kaveh",
        description="Kaveh quality-first proxy feed pipeline",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)
    ingest = subcommands.add_parser("ingest", help="fetch, normalize, parse, and deduplicate sources")
    ingest.add_argument(
        "--registry",
        type=Path,
        default=Path("configs/sources/registry.v1.json"),
        help="path to a reviewed source registry",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "ingest":
        sources = load_sources(args.registry)
        repository = InMemoryConfigRepository()
        report = IngestSources(
            BoundedHttpsSourceClient(), ParserRegistry(), repository
        ).run(sources)
        print(
            json.dumps(
                {
                    "discovered": report.discovered_count,
                    "parsed": report.parsed_count,
                    "duplicates": report.duplicate_count,
                    "rejected": report.rejected_count,
                    "source_errors": report.source_errors,
                    "rejection_codes": report.rejection_codes,
                },
                sort_keys=True,
            )
        )
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
