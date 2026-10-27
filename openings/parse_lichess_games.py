#!/usr/bin/env python3
"""Build a frequency list of opening lines from one monthly Lichess PGN file.

See docs/matches_openings.md for the full specification.
"""

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
from compression import zstd

# Bump when a change would alter the output of a build.
SCRIPT_VERSION = 1

TIME_CONTROLS = ("Blitz", "Rapid")
# An eligible game's Event header contains one of these exact phrases. Matches
# docs/matches_openings.md: "Rated Blitz game" or "Rated Rapid game". Tournament
# games (e.g. "Rated Blitz tournament <url>") do not contain these and are excluded.
ELIGIBLE_EVENTS = ("Rated Blitz game", "Rated Rapid game")

# A SAN token after stripping check/mate/annotation marks and move numbers.
RESULTS = ("1-0", "0-1", "1/2-1/2", "*")
SUFFIX_CHARS = str.maketrans("", "", "+#!?")


def list_id(month, k, p, f):
    """Build the frequency list ID from its parameters.

    month is YYYY-MM; the ID keeps the hyphen as YYYY-MM.
    """
    return f"freq-{month}-k{k}-p{p}-f{f}"


def parse_elo(value):
    """Return the Elo as an int, or None if missing or '?'."""
    if value is None or value == "?":
        return None
    try:
        return int(value)
    except ValueError:
        return None


def event_eligible(event):
    return any(phrase in event for phrase in ELIGIBLE_EVENTS)


def iter_games(lines):
    """Yield (headers, movetext) for each game in a stream of text lines.

    A game is a block of header lines followed by movetext lines, separated by
    blank lines. This follows the PGN layout: a header section, a blank line,
    a movetext section, and a blank line.
    """
    headers = {}
    movetext_parts = []
    in_movetext = False
    for line in lines:
        line = line.rstrip("\n")
        if line.startswith("["):
            if in_movetext:
                # A new game's headers begin; emit the one we were building.
                yield headers, " ".join(movetext_parts)
                headers = {}
                movetext_parts = []
                in_movetext = False
            m = re.match(r'\[(\w+)\s+"(.*)"\]', line)
            if m:
                headers[m.group(1)] = m.group(2)
        elif line.strip() == "":
            if movetext_parts:
                in_movetext = True
        else:
            in_movetext = True
            movetext_parts.append(line.strip())
    if headers or movetext_parts:
        yield headers, " ".join(movetext_parts)


def extract_moves(movetext, limit):
    """Return up to `limit` SAN tokens from movetext.

    Skips {...} comments, nested ( ... ) variations, $n NAGs, move numbers, and
    results. Strips + # ! ? from each SAN token. Stops once `limit` tokens are
    collected. Returns fewer than `limit` only when the game has fewer plies.
    """
    moves = []
    depth = 0  # nesting depth of ( ... ) variations
    in_comment = False
    i = 0
    n = len(movetext)
    token = []

    def flush():
        if not token:
            return
        tok = "".join(token)
        token.clear()
        if depth > 0:
            return
        if tok in RESULTS or tok.startswith("$"):
            return
        # Move numbers: "1.", "1...", or a bare number before a move.
        stripped = tok.rstrip(".")
        if stripped.isdigit():
            return
        # A token like "1.e4" has the number glued to the move; split it off.
        san = tok.lstrip("0123456789.")
        if not san:
            return
        san = san.translate(SUFFIX_CHARS)
        if san:
            moves.append(san)

    while i < n and len(moves) < limit:
        c = movetext[i]
        if in_comment:
            if c == "}":
                in_comment = False
            i += 1
            continue
        if c == "{":
            flush()
            in_comment = True
            i += 1
            continue
        if c == "(":
            flush()
            depth += 1
            i += 1
            continue
        if c == ")":
            flush()
            if depth > 0:
                depth -= 1
            i += 1
            continue
        if c.isspace():
            flush()
            i += 1
            continue
        token.append(c)
        i += 1
    if len(moves) < limit:
        flush()
    return moves[:limit]


def count_games(path, k, p, db):
    """Stream the PGN file and count games per P-move line in SQLite.

    Returns the number of eligible games kept.
    """
    cur = db.cursor()
    cur.execute("CREATE TABLE lines (key TEXT PRIMARY KEY, count INTEGER NOT NULL)")
    kept = 0
    with open(path, "rb") as raw:
        with zstd.ZstdFile(raw, "rb") as fobj:
            import io

            text = io.TextIOWrapper(fobj, encoding="utf-8", errors="replace")
            for headers, movetext in iter_games(text):
                if not headers:
                    continue
                if not event_eligible(headers.get("Event", "")):
                    continue
                white = parse_elo(headers.get("WhiteElo"))
                black = parse_elo(headers.get("BlackElo"))
                if white is None or black is None or white < k or black < k:
                    continue
                moves = extract_moves(movetext, p)
                if len(moves) < p:
                    continue
                key = " ".join(moves)
                cur.execute(
                    "INSERT INTO lines (key, count) VALUES (?, 1) "
                    "ON CONFLICT(key) DO UPDATE SET count = count + 1",
                    (key,),
                )
                kept += 1
    db.commit()
    return kept


def top_lines(db, f):
    """Return the F most common (key, count) pairs, ties broken by ascending key.

    Order is by count descending, then key ascending.
    """
    cur = db.cursor()
    cur.execute(
        "SELECT key, count FROM lines ORDER BY count DESC, key ASC LIMIT ?", (f,)
    )
    return cur.fetchall()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fobj:
        for chunk in iter(lambda: fobj.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build(month, k, p, f, data_dir, out_dir, source_path=None):
    lid = list_id(month, k, p, f)
    pgn_path = os.path.join(out_dir, lid + ".pgn")
    json_path = os.path.join(out_dir, lid + ".json")
    if os.path.exists(pgn_path) or os.path.exists(json_path):
        raise FileExistsError(f"output already exists for list {lid}")

    if source_path is None:
        source_path = os.path.join(
            data_dir, f"lichess_db_standard_rated_{month}.pgn.zst"
        )
    if not os.path.exists(source_path):
        raise FileNotFoundError(source_path)

    db_path = os.path.join(data_dir, lid + ".sqlite")
    if os.path.exists(db_path):
        raise FileExistsError(db_path)

    db = sqlite3.connect(db_path)
    try:
        kept = count_games(source_path, k, p, db)
        cur = db.cursor()
        cur.execute("SELECT COUNT(*) FROM lines")
        distinct = cur.fetchone()[0]
        if distinct < f:
            raise ValueError(
                f"only {distinct} lines qualified, need {f}"
            )
        rows = top_lines(db, f)
    finally:
        db.close()

    os.makedirs(out_dir, exist_ok=True)
    with open(pgn_path, "w", encoding="utf-8") as fobj:
        for key, _count in rows:
            fobj.write(key + "\n")

    metadata = {
        "list_id": lid,
        "source_file_name": os.path.basename(source_path),
        "source_sha256": sha256_file(source_path),
        "k": k,
        "p": p,
        "f": f,
        "source_month": month,
        "time_controls": list(TIME_CONTROLS),
        "games_kept": kept,
        "distinct_lines_seen": distinct,
        "fth_line_count": rows[-1][1],
        "script_version": SCRIPT_VERSION,
    }
    with open(json_path, "w", encoding="utf-8") as fobj:
        json.dump(metadata, fobj, indent=2, sort_keys=True)
        fobj.write("\n")

    # Delete the temporary database only after a successful build.
    os.remove(db_path)
    return lid


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--month", default="2026-09")
    parser.add_argument("--k", type=int, default=2000)
    parser.add_argument("--p", type=int, default=16)
    parser.add_argument("--f", type=int, default=1024)
    args = parser.parse_args(argv)

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(repo_root, "data")
    out_dir = os.path.join(repo_root, "openings")
    lid = build(args.month, args.k, args.p, args.f, data_dir, out_dir)
    print(f"wrote {lid}")


if __name__ == "__main__":
    sys.exit(main())
