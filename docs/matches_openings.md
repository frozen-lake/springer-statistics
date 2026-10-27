# Matches: opening list

Plan for the opening list that [Matches](matches.md) plays from. Not yet built. Every value below is proposed unless marked decided.

## Source

- **Lichess open database** of rated standard games, at [database.lichess.org](https://database.lichess.org/). The CC0 1.0 text is in [lichess-org/files](https://github.com/lichess-org/files/blob/lichess/LICENSE), which Lichess links for its data. Confirm that the database page names CC0 before the first build.
- One monthly PGN file per frequency list. The first list uses September 2026. The month is a setting in `parse_lichess_games.py`. Record its file name and SHA-256.

## Build (proposed)

This produces the frequency list. It is immutable: once written, it is never changed.

1. Stream the monthly file through a decompressor. Do not load the whole file into memory.
2. For each game, keep it only if it is a rated Blitz or Rapid game, both players have an Elo header of at least `K`, and it has at least `P` plies.
3. Read the first `P` moves as SAN tokens, skipping comments, variations, move numbers, and results. The moves are not replayed, so no chess library is needed.
4. Count how many games reached each `P`-move line. Counting uses a temporary SQLite database in `data/`, which is deleted after a successful build. Counts are exact, and memory stays bounded.
5. Keep the `F` most common lines. Break ties by the move text, so the result is the same on every build.
6. Write the lines in frequency order, most common first, as a PGN file. fastchess reads this with `format=pgn`.
7. Record the metadata listed under Reproducibility.

## Shuffled list (proposed)

A separate script makes the list that runs use. It reads one frequency list and writes a new list.

1. Choose a seed and a size `M`.
2. Take a random subset of `M` lines from the frequency list, then shuffle them with that seed. The subset may leave out some lines.
3. Write them as a PGN file with a new list ID.
4. Record the frequency list ID, the seed, and `M`.

Shuffling means the first 64 and first 512 lines that runs use are a random sample of the frequency list, not only the most common lines.

## Parameters

| Parameter | Value | Status |
|-----------|-------|--------|
| `K`, minimum rating of both players | 2000 | Decided |
| `P`, plies per line | 16 | Decided |
| `F`, lines in the frequency list | 1024 | Decided for now |
| Source month | September 2026 (configurable in `parse_lichess_games.py`) | Decided |
| Time controls | Blitz and Rapid | Decided |
| Shuffled list size `M` | 512 for the first shuffle | Decided |
| Commit the lists to the repo | Yes, in `openings/` (`.gitignore` exception added) | Decided |

There is no minimum-count rule. The `F` most common lines are kept, and the build records the count of the `F`th line. A very small count there means the month is too thin for that `K`.

## Size

Runs use the first 512 lines of the shuffled list for A/B and the first 64 for A/A. The shuffled list must have at least 512 lines. The frequency list has `F` = 1024 lines. The count is recorded at build time.

## Script specification

Both scripts live in `openings/`, next to the lists they write. Each is a standalone Python script that uses only the standard library.

**`parse_lichess_games.py`** builds the frequency list.

- Input: the monthly file `lichess_db_standard_rated_<YYYY-MM>.pgn.zst`, read from `data/` (ignored by git). Confirm the exact name on the download page.
- Eligible game: `Event` header contains "Rated Blitz game" or "Rated Rapid game" (confirm the exact text on a real file), `WhiteElo` and `BlackElo` are both at least `K`, and the game has at least `P` plies. Missing Elo or `?` means not eligible.
- Move text: skip `{...}` comments (including `[%clock]` and `[%eval]`), nested `( ... )` variations, `$n` NAG codes, move numbers, and results. Strip `+`, `#`, `!`, and `?` from each SAN token.
- Line key: the first `P` SAN tokens joined by single spaces. Count games per key. Keep the `F` highest counts, and break ties by ascending key.
- Output: `openings/<list_id>.pgn`, with lines in frequency order. Each line is one game containing only the `P` moves. The format must be read correctly by `fastchess -openings format=pgn plies=P`, and the build checks this on the fixture.
- Refuse to overwrite an existing list. Fail if fewer than `F` lines qualify.
- Source month and `K`, `P`, `F` are set by command-line arguments, with the values above as defaults.

**`shuffle_openings_list.py`** builds the shuffled list.

- Input: one frequency list. Output: `openings/<list_id>.pgn`.
- Use `random.Random(seed)`: take a random sample of `M` lines from the frequency list, then shuffle the sample.
- Fail if `M` is larger than the frequency list, or if the output already exists.

**Metadata.** Each list has a JSON file next to it, `openings/<list_id>.json`, which holds the metadata listed under Reproducibility.

**Tests.** Standard `unittest`. A hand-made fixture PGN with expected counts, order, and shuffle results worked out by hand, and tests for the parser rules, eligibility, tie-breaks, shuffle determinism, and overwrite refusal. The expected values must be stated in the tests with their source.

## Tooling

- Python 3.14 is required for both the submission CLI and the openings scripts. The openings scripts use `compression.zstd`, and the CLI runs on the host, not in the Docker image.
- Parsing uses only the standard library.
- Command-line arguments (decided):
  - `parse_lichess_games.py`: `--month YYYY-MM` (default `2026-09`), `--k` (default `2000`), `--p` (default `16`), `--f` (default `1024`). Output goes to `openings/`.
  - `shuffle_openings_list.py`: `--freq <ID>` (required, full or numeric), `--seed <int>` (required, no default), `--m` (default `512`). Output goes to `openings/`.
  - Neither script has a `--force` flag. An existing list is never overwritten.

## List IDs

Each list has a full ID, which is readable, and a numeric ID, which encodes the same fields in fixed-width digits. The fixed-width scheme is decided. Both name the same list. Scripts accept either form.

**Frequency lists**

- Full ID: `freq-2026-09-k2000-p16-f1024`. This is also the file name, `openings/freq-2026-09-k2000-p16-f1024.pgn`.
- Numeric ID: `YYYYMM` (6 digits), then `K` (4 digits), `P` (2 digits), `F` (4 digits). The example is `2026092000161024`.
- Ranges: year 2013–9999, month 01–12, `K` 1000–9999, `P` 01–99, `F` 0001–9999. Values outside these ranges are rejected, so every full ID maps to exactly one numeric ID and back.
- The numeric ID is decoded by slicing: characters 1–6 are the month, 7–10 are `K`, 11–12 are `P`, and 13–16 are `F`.
- Time controls are not encoded. Frequency lists are Blitz and Rapid only. A list with other time controls needs a different prefix.

**Shuffled lists**

- Full ID: `shuf-<numeric frequency ID>-seed<seed>-m<M>`. The example is `shuf-2026092000161024-seed42-m512`, with file name `openings/shuf-2026092000161024-seed42-m512.pgn`.
- The frequency part always uses the numeric ID, so the shuffled ID stays short.
- The seed and `M` are written as plain numbers.

A round-trip test checks that every valid full ID encodes and decodes to the same fields, and that out-of-range values are rejected.

## Reproducibility

Each frequency list records:

- list ID, source file name, and source SHA-256
- `K`, `P`, `F`, source month, time controls
- games kept, distinct lines seen, and the count of the `F`th line
- the build script version

Each shuffled list records the frequency list ID, the seed, `M`, and the build script version.

Lists are never modified. A change creates a new list ID.

