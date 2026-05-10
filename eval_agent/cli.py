"""CLI for the evaluation agent.

Reads an AssessmentItem JSON from a file (or stdin), takes the student's
response, and emits a TraceEvent.

Usage:

    # Text response
    python -m eval_agent.cli --item item.json --session sess_001 \
        --response "Una catena di Markov è ..." [--pro]

    # Response read from a file
    python -m eval_agent.cli --item item.json --session sess_001 \
        --response-file response.txt

    # Audio response (Phase 4)
    python -m eval_agent.cli --item item.json --session sess_001 \
        --response audio.mp3 --modality audio
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from eval_agent.models import AssessmentItem, ResponseModality
from eval_agent.orchestrator import evaluate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="eval_agent",
        description=(
            "Evaluate a student response to a single AssessmentItem. "
            "Produces a TraceEvent JSON in data/traces/<session_id>/."
        ),
    )
    parser.add_argument(
        "--item", required=True, type=Path,
        help="Path to a JSON file with the AssessmentItem to evaluate against.",
    )
    parser.add_argument(
        "--session", dest="session_id", required=True,
        help="Session identifier. Drives two-strikes rule + trace directory.",
    )
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument(
        "--response", help="The student's response (text), OR a path to an audio file when --modality audio.",
    )
    src.add_argument(
        "--response-file", type=Path,
        help="Read the student's text response from this file.",
    )
    parser.add_argument(
        "--modality", choices=["text", "audio"], default="text",
        help="Response modality. Default: text.",
    )
    parser.add_argument(
        "--pro", action="store_true",
        help=(
            "Use Gemini 2.5 Pro for the judge_open node only. Reads "
            "GEMINI_PRO_API_KEY (separate from GOOGLE_API_KEY)."
        ),
    )
    parser.add_argument(
        "--api", dest="api_key", default=None, metavar="KEY",
        help="Override GOOGLE_API_KEY for this run. Prefer .env for keys you reuse.",
    )
    parser.add_argument(
        "--api-pro", dest="api_pro_key", default=None, metavar="KEY",
        help="Override GEMINI_PRO_API_KEY for this run. Only used with --pro.",
    )
    parser.add_argument(
        "--paralinguistic-file", type=Path, default=None, metavar="JSON",
        help=(
            "TEST/DEMO ONLY. Inject pre-computed paralinguistic features "
            "from a JSON file, bypassing the audio transcription + "
            "extraction pipeline. Useful to demonstrate that the same "
            "verbatim response gets a different elaborazione score when "
            "paired with paralinguistic signals (self-corrections, pauses, "
            "reformulations)."
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

    if args.api_key:
        os.environ["GOOGLE_API_KEY"] = args.api_key
    if args.api_pro_key:
        os.environ["GEMINI_PRO_API_KEY"] = args.api_pro_key

    item = AssessmentItem.model_validate_json(args.item.read_text(encoding="utf-8"))

    if args.response_file:
        response_str: str = args.response_file.read_text(encoding="utf-8").strip()
    else:
        response_str = args.response

    paralinguistic = None
    if args.paralinguistic_file:
        paralinguistic = json.loads(
            args.paralinguistic_file.read_text(encoding="utf-8")
        )

    payload = evaluate(
        item,
        response_str,
        session_id=args.session_id,
        response_modality=ResponseModality(args.modality),
        use_pro=args.pro,
        paralinguistic_features=paralinguistic,
    )

    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
