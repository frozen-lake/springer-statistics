#!/usr/bin/env python3
"""Build a shuffled opening list from one frequency list.

See docs/matches_openings.md for the full specification.
"""

import argparse
import json
import os
import random
import sys

# Bump when a change would alter the output of a build.
SCRIPT_VERSION = 1


def list_id(freq_id, seed, m):
    """Build the shuffled list ID from its parameters."""
    return f"shuf-{freq_id}-seed{seed}-m{m}"


def shuffle_lines(lines, seed, m):
    """Return the first M lines of a seeded shuffle of a copy of `lines`.

    The input list is not modified.
    """
    shuffled = list(lines)
    random.Random(seed).shuffle(shuffled)
    return shuffled[:m]


def build(freq_id, seed, m, out_dir):
    lid = list_id(freq_id, seed, m)
    pgn_path = os.path.join(out_dir, lid + ".pgn")
    json_path = os.path.join(out_dir, lid + ".json")
    if os.path.exists(pgn_path) or os.path.exists(json_path):
        raise FileExistsError(f"output already exists for list {lid}")

    freq_path = os.path.join(out_dir, freq_id + ".pgn")
    if not os.path.exists(freq_path):
        raise FileNotFoundError(freq_path)

    with open(freq_path, "r", encoding="utf-8") as fobj:
        lines = [line.rstrip("\n") for line in fobj if line.strip()]

    if m > len(lines):
        raise ValueError(f"M={m} is larger than the frequency list ({len(lines)} lines)")

    selected = shuffle_lines(lines, seed, m)

    os.makedirs(out_dir, exist_ok=True)
    with open(pgn_path, "w", encoding="utf-8") as fobj:
        for line in selected:
            fobj.write(line + "\n")

    metadata = {
        "list_id": lid,
        "frequency_list_id": freq_id,
        "seed": seed,
        "m": m,
        "script_version": SCRIPT_VERSION,
    }
    with open(json_path, "w", encoding="utf-8") as fobj:
        json.dump(metadata, fobj, indent=2, sort_keys=True)
        fobj.write("\n")
    return lid


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freq", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--m", type=int, default=512)
    args = parser.parse_args(argv)

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_dir = os.path.join(repo_root, "openings")
    lid = build(args.freq, args.seed, args.m, out_dir)
    print(f"wrote {lid}")


if __name__ == "__main__":
    sys.exit(main())
