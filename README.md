# Springer Statistics

Measurement tools for testing the strength and quality of [Springer](https://github.com/frozen-lake/Springer), a UCI chess engine written in C.

## Status

Early development and planning; nothing is usable yet.

## Terminology

- Baseline engine: a reference version of Springer, specified as a branch name and commit hash, defaulting to the latest commit on `main`.
- Candidate engine: a version of Springer with changes to evaluate, specified as a branch name and commit hash.

## Tools

### Matches

Plays a baseline and a candidate build of Springer against the same strength-limited Stockfish, over the same ordered list of opening positions.

- Openings come from rated Blitz and Rapid games in the [Lichess database](https://database.lichess.org/), which is released under CC0. The most common 16-ply lines are recorded as a frequency list, which is never changed. A random subset is then selected using a recorded seed and saved as a fixed, ordered opening list with its own ID, so that runs can be repeated.
- Baseline and candidate each play a configurable number of games against identical Stockfish settings, from the same opening list.

Per-run recorded data includes:
- The hardware on which the games were run.
- The number of concurrent games per match.
- The branch name and commit hash, for both the baseline and candidate engine.
- Timestamps for when the run began and when it finished.
- The time control of the matches.
- The opening list used.
- The Stockfish Elo, version, and settings used.
- The result of each game, for both the baseline and candidate engine, with the opening, game length in plies, color played, and how each game ended (checkmate, timeout, stalemate, repetition, fifty-move rule, insufficient material, crash, illegal move).
- The total nodes searched and nodes per second for each engine in each game.
- The latency reported for each engine (mean and maximum), which shows the overhead the tool adds to each engine's time.

How the recorded data will be analyzed is not yet decided.

### Positions

Measures move quality across a large number of positions.

- Positions are sampled from games in the [Lichess database](https://database.lichess.org/) using a recorded seed and saved as a fixed position set, identified by that seed, so that runs can be repeated.
- The baseline and candidate engines both analyze every position.
- Analysis compares average centipawn loss (ACPL) between baseline and candidate, using a single, consistent pre-recorded Stockfish evaluation for every legal move in each position as the reference.
- The Stockfish version and settings used for analysis are recorded alongside the evaluation run.

Per-run recorded data includes:
- The hardware on which the analyses were run.
- The number of concurrent analyses.
- The branch name and commit hash, for both the baseline and candidate engine.
- Timestamps for when the run began and when it finished.
- The time and depth limits given to the baseline and candidate engines.
- An identifier for the set of positions evaluated.
- The baseline and candidate engines' chosen move in each position.

Post-run analysis includes:
- An identifier for the reference evaluation used.
- The baseline and candidate engines' centipawn loss in each of the positions evaluated.
- The baseline and candidate engines' average centipawn loss across all positions evaluated.

## License

Licensed under the GNU General Public License v3.0. See [LICENSE](LICENSE).
