# Matches: opening list

Specification for the opening list that [Matches](matches.md) plays from. The scripts that build it are in `openings/`. Values marked Decided are settled; the rest are proposed.

## Source

- **Lichess open database** of rated standard games, at [database.lichess.org](https://database.lichess.org/). The CC0 1.0 text is in [lichess-org/files](https://github.com/lichess-org/files/blob/lichess/LICENSE), which Lichess links for its data. Checked: the download page states that database exports are released under CC0.
- One monthly PGN file per frequency list. The first list uses September 2026. The month is set with `--month` on `parse_lichess_games.py`. Record its file name and SHA-256.

## Build

This produces the frequency list. It is immutable: once written, it is never changed.

1. Stream the monthly file through a decompressor. Do not load the whole file into memory.
2. For each game, keep it only if it is a rated Blitz or Rapid game, both players have an Elo header of at least `K`, and it has at least `P` plies.
3. Read the first `P` moves as SAN tokens, skipping comments, variations, move numbers, and results. The moves are not replayed, so no chess library is needed.
4. Count how many games reached each `P`-move line. Counting uses a temporary SQLite database in `data/`, which is deleted after a successful build. Counts are exact, and memory stays bounded.
5. Keep the `F` most common lines. Break ties by the move text, so the result is the same on every build.
6. Write the lines in frequency order, most common first, as a PGN file. Each line is one complete game: an `[Event "?"]` header, the `P` moves with move numbers, and `*` as the result, for example `[Event "?"] 1. e4 e5 2. Nf3 Nc6 *`. fastchess 1.8.2 rejects games without a header.
7. Record the metadata listed under Reproducibility.

## Shuffled list

A separate script makes the list that runs use. It reads one frequency list and writes a new list.

1. Choose a seed and a size `M`.
2. Take the first `M` lines of the frequency list, which are the `M` most common. Shuffle that set with a random generator seeded with that seed. The frequency list is not changed.
3. Write them as a PGN file with a new list ID.
4. Record the frequency list ID, the seed, and `M`.

The shuffle changes only the order. The lines used are always the `M` most common. The first 64 and first 512 lines that runs use are a random order of those lines, so an A/A run of 64 takes 64 random lines from the top 512.

## Parameters

| Parameter | Value | Status |
|-----------|-------|--------|
| `K`, minimum rating of both players (`--k`) | 2000 | Decided |
| `P`, plies per line (`--p`) | 6 | Decided |
| `F`, lines in the frequency list (`--f`) | 1024 | Decided for now |
| Source month (`--month`) | September 2026 | Decided |
| Time controls | Blitz and Rapid | Decided |
| Shuffled list size `M` (`--m`) | 512 for the first shuffle | Decided |
| Commit the lists to the repo | Yes, in `openings/` (nothing in `.gitignore` excludes them) | Decided |

There is no minimum-count rule. The `F` most common lines are kept, and the build records the count of the `F`th line. A very small count there means the month is too thin for that `K`.

## Size

Runs use the first 512 lines of the shuffled list for A/B and the first 64 for A/A. The shuffled list must have at least 512 lines. The frequency list has `F` = 1024 lines. The count is recorded at build time.

## Script specification

Both scripts live in `openings/`, next to the lists they write. Each is a standalone Python script that uses only the standard library.

**`parse_lichess_games.py`** builds the frequency list.

- Input: the monthly file `lichess_db_standard_rated_<YYYY-MM>.pgn.zst`, read from `data/` (ignored by git). The URL `https://database.lichess.org/standard/lichess_db_standard_rated_<YYYY-MM>.pgn.zst` worked for 2026-09.
- Eligible game: `Event` header contains "Rated Blitz game" or "Rated Rapid game" (confirmed on a 2,000-game sample of the 2026-09 file; tournament games, with headers such as "Rated Blitz tournament <url>", do not match and are excluded by decision), `WhiteElo` and `BlackElo` are both at least `K`, and the game has at least `P` plies. Missing Elo or `?` means not eligible.
- Move text: skip `{...}` comments (including `[%clock]` and `[%eval]`), nested `( ... )` variations, `$n` NAG codes, move numbers, and results. Strip `+`, `#`, `!`, and `?` from each SAN token.
- Line key: the first `P` SAN tokens joined by single spaces. Count games per key. Keep the `F` highest counts, and break ties by ascending key.
- Output: `openings/<list_id>.pgn`, with lines in frequency order. Each line is one complete game: an `[Event "?"]` header, the `P` moves with move numbers, and `*` as the result. The format is meant to be read by `fastchess -openings format=pgn plies=P`, which is `plies=6` for the current list. The agent cannot run fastchess, so the maintainer checks this locally.
- Refuse to overwrite an existing list. Fail if fewer than `F` lines qualify.
- Source month, `K`, `P`, and `F` are set by command-line arguments (`--month`, `--k`, `--p`, `--f`), with the values above as defaults.

**`shuffle_openings_list.py`** builds the shuffled list.

- Input: one frequency list. Output: `openings/<list_id>.pgn`.
- Use `random.Random(seed)`: take the first `M` lines of the frequency list (the `M` most common), then shuffle that copy in place.
- Fail if `M` is larger than the frequency list, or if the output already exists.

**Metadata.** Each list has a JSON file next to it, `openings/<list_id>.json`, which holds the metadata listed under Reproducibility.

**Tests.** Standard `unittest`. A hand-made fixture PGN with expected counts and order worked out by hand, and tests for the parser rules, eligibility, tie-breaks, shuffle determinism, and overwrite refusal. Expected counts and order must be stated in the tests with their source. Shuffle output is not checked against hand-worked values; the shuffle tests check properties instead: `M` lines, each from the first `M` lines of the frequency list with no repeats, the same seed gives the same output, and a different seed gives a different output.

## Tooling

- Python 3.14 is required for both the submission CLI and the openings scripts. The openings scripts use `compression.zstd`, and the CLI runs on the host, not in the Docker image.
- Parsing uses only the standard library.
- Command-line arguments (decided):
  - `parse_lichess_games.py`: `--month YYYY-MM` (default `2026-09`), `--k` (default `2000`), `--p` (default `6`), `--f` (default `1024`). Output goes to `openings/`.
  - `shuffle_openings_list.py`: `--freq <ID>` (required, full frequency ID), `--seed <int>` (required, no default), `--m` (default `512`). Output goes to `openings/`.
  - Neither script has a `--force` flag. An existing list is never overwritten.

## List IDs

Each list's ID is built from its parameters, and its file name is the ID plus `.pgn`. Each script builds the ID with a format string. There are no numeric IDs and no range checks.

**Frequency lists**

- ID: `freq-<YYYY>-<MM>-k<K>-p<P>-f<F>`. The example is `freq-2026-09-k2000-p6-f1024`, with file name `openings/freq-2026-09-k2000-p6-f1024.pgn`.
- Frequency lists are Blitz and Rapid only. A list with other time controls needs a different prefix.

**Shuffled lists**

- ID: `shuf-<frequency ID>-seed<seed>-m<M>`. The example is `shuf-freq-2026-09-k2000-p6-f1024-seed42-m512`, with file name `openings/shuf-freq-2026-09-k2000-p6-f1024-seed42-m512.pgn`.
- `--freq` takes the full frequency ID only.

## Reproducibility

Each frequency list records:

- list ID, source file name, and source SHA-256
- `K`, `P`, `F`, source month, time controls
- games kept, distinct lines seen, and the count of the `F`th line
- the build script version

Each shuffled list records the frequency list ID, the seed, `M`, and the build script version.

Lists are never modified. A change creates a new list ID.

