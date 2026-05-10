"""CLI for the quiz generator.

Usage examples:

  # 5 flashcards from a raw text file (medium difficulty)
  python -m quiz_creation_agent.cli notes.md --type f --n 5 -o out.json

  # 3 hard MCQs from a specific section of an index.json
  python -m quiz_creation_agent.cli idx.json --node n_3_2 --type mcq --n 3 \
      --difficulty hard -o quiz.json

  # 4 easy open questions, force English language
  python -m quiz_creation_agent.cli paper.txt --type qa --n 4 \
      --difficulty easy --lang en -o openq.json
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from quiz_creation_agent.models import Difficulty, ItemType
from quiz_creation_agent.orchestrator import generate_quiz


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="quiz_creation_agent",
        description=(
            "Generate flashcards, MCQs, or open questions from a passage. "
            "Input can be a raw text file (.txt/.md) or an indexing-agent "
            "JSON paired with --node."
        ),
    )
    parser.add_argument(
        "input", type=Path,
        help="Path to a .txt/.md file (raw text), or .json index file (with --node).",
    )
    parser.add_argument(
        "--type", dest="item_type", required=True,
        choices=[t.value for t in ItemType],
        help="Item type: f=flashcard, mcq=multiple-choice, qa=open question.",
    )
    parser.add_argument(
        "--n", dest="n", type=int, required=True,
        help="Number of items to generate.",
    )
    parser.add_argument(
        "--difficulty", default=Difficulty.MEDIUM.value,
        choices=[d.value for d in Difficulty],
        help="Difficulty level. Default: medium.",
    )
    parser.add_argument(
        "--node", dest="node_id", default=None,
        help="Required when input is an indexing-agent JSON. Picks the section/paragraph to quiz on.",
    )
    parser.add_argument(
        "--lang", dest="language", default=None, choices=["it", "en"],
        help="Force language. Default: auto-detect (from index.json source, or from text).",
    )
    parser.add_argument(
        "-o", "--output", type=Path, default=None,
        help="Where to write the quiz JSON. If omitted, prints to stdout.",
    )
    parser.add_argument(
        "--api", dest="api_key", default=None, metavar="KEY",
        help=(
            "Gemini API key for this run. Overrides GOOGLE_API_KEY / "
            "GEMINI_API_KEY / .env. Note: passing a key on the command line "
            "records it in shell history — prefer .env for keys you reuse."
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

    payload = generate_quiz(
        args.input,
        item_type=ItemType(args.item_type),
        n=args.n,
        difficulty=Difficulty(args.difficulty),
        node_id=args.node_id,
        language=args.language,
        output_path=args.output,
    )

    if args.output is None:
        json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    else:
        print(f"Wrote {args.output}  ({payload['n_produced']}/{payload['n_requested']} items)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
