"""Command-line entry point.

Usage:
    python -m agent.cli <input> [-o <output.json>] [--type pdf_notes|pdf_slides|...]

The CLI is a thin wrapper around `index_document` for ad-hoc testing. The
real consumer is the FastAPI backend, which imports `index_document`
directly.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from agent.models import SourceType
from agent.orchestrator import index_or_aggregate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="agent",
        description=(
            "Index a study document, or aggregate a folder of indexed JSONs. "
            "If the input path is a file, the document is indexed. If it is "
            "a directory, every valid index.json inside is aggregated into a "
            "cross-document tree."
        ),
    )
    parser.add_argument(
        "input", type=Path,
        help="Path to a source file, OR a folder of agent-output JSONs to aggregate.",
    )
    parser.add_argument(
        "-o", "--output", type=Path, default=None,
        help="Where to write index.json. If omitted, prints to stdout.",
    )
    parser.add_argument(
        "--type", dest="source_type", default=None,
        choices=[t.value for t in SourceType],
        help="Force a source type (e.g. pdf_notes, pdf_slides).",
    )
    parser.add_argument(
        "--novad", action="store_true",
        help=(
            "Disable Whisper's VAD silence filter. Useful for sung audio or "
            "speech with a music bed, where VAD discards real content. "
            "Equivalent to AGENT_WHISPER_VAD=false."
        ),
    )
    parser.add_argument(
        "--api", dest="api_key", default=None, metavar="KEY",
        help=(
            "Gemini API key for this run. Overrides GOOGLE_API_KEY / "
            "GEMINI_API_KEY / .env. If omitted, those are used. "
            "Note: passing a key on the command line records it in shell "
            "history — prefer .env for keys you reuse."
        ),
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Verbose logging.",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if args.novad:
        os.environ["AGENT_WHISPER_VAD"] = "false"
    if args.api_key:
        os.environ["GOOGLE_API_KEY"] = args.api_key

    src_type = SourceType(args.source_type) if args.source_type else None
    payload = index_or_aggregate(
        args.input, source_type=src_type, output_path=args.output
    )

    if args.output is None:
        json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    else:
        print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
