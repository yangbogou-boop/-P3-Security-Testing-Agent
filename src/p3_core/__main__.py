"""python -m p3_core --config examples/offline.json --output <new-run-root>"""
import argparse
import json
from pathlib import Path
import sys

from .controller import Controller
from .evidence import JsonlEvidence


def main(argv=None):
    parser = argparse.ArgumentParser(description="P3 offline control validation (no HTTP)")
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        raw = json.loads(Path(args.config).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        print("INVALID_INPUT: cannot read configuration", file=sys.stderr)
        return 2
    report = Controller(raw, evidence=JsonlEvidence(args.output)).run()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["audit_gap"]:
        print("AUDIT_ERROR: evidence incomplete; no further dispatch", file=sys.stderr)
        return 3
    return 0 if report["state"] == "COMPLETED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
