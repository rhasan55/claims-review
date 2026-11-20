"""Validate a candidate JSON file from an approved model or a human author.

Usage: python evaluate_candidate.py candidate.json
The example claim is synthetic and lives in evidence.py. No network calls.
"""

import argparse, json
from pathlib import Path
from evidence import BASE, validate


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("candidate", type=Path)
    a = p.parse_args()
    try:
        candidate = json.loads(a.candidate.read_text())
    except (ValueError, OSError) as e:
        p.exit(2, f"Cannot load candidate JSON: {e}\n")
    print(json.dumps(validate(BASE, candidate), indent=2))


if __name__ == "__main__":
    main()
