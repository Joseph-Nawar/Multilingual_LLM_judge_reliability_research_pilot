#!/usr/bin/env python3
"""Run and analyze the separately frozen Paper 2 state-access diagnostic."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
PRIVATE_ROOT = (REPO_ROOT / ".research-data").resolve()
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from multilingual_judge_pilot.local_ollama import OllamaLocalClient
from multilingual_judge_pilot.paper2_state_access import StateAccessError, run_locked_state_access


def _private_path(value: str | Path) -> Path:
    path = Path(value).expanduser().resolve()
    if not path.is_relative_to(PRIVATE_ROOT):
        raise StateAccessError("locked state-access freeze paths must remain under repository .research-data/")
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="run or resume the frozen local diagnostic")
    run.add_argument("--freeze-root", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        freeze_root = _private_path(args.freeze_root)
        if args.command == "run":
            result = run_locked_state_access(freeze_root, OllamaLocalClient(timeout_seconds=600))
        else:
            raise StateAccessError("unsupported command")
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
