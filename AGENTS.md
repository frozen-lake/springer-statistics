# Agent Instructions

Read [README.md](README.md) first for the project's goals.

## Ownership

The maintainer wants to understand and own every line of code. Prefer small, simple, readable changes over complete or clever ones.

Do only what the task asks. Do not add features, refactors, or "improvements" beyond its scope.

**Stop and ask** before making any decision that:

- affects whether measurements are valid (statistics, sampling, engine or Stockfish settings, test conditions)
- defines a format or interface others will depend on (result schemas, file formats, CLI arguments, module boundaries)
- adds a dependency, external tool, or service
- affects infrastructure, security, or cost (AWS, credentials, storage)
- would be hard to undo

## Measurement Integrity

These rules apply to every measurement tool in this repository.

- Anything being compared (for example, baseline and candidate) is measured under the same conditions: the same input data, the same reference engine and settings, the same search or time limits, the same number of concurrent games, and the same machine type.
- Saved datasets that runs depend on, such as a fixed opening set or set of Stockfish reference evaluations, are never modified. Any change instead creates a new version with a new identifier.
- Every run records what is needed to reproduce it.
- Results are never overwritten or deleted. Each run is stored separately.

## Working Style

- Keep each change to one task and one concern.
- When presenting your work, explain non-obvious choices, including alternatives you considered.
- Comment only to explain non-obvious reasoning or assumptions that any reader of the code needs to understand.
- Add tests for new logic that affects measurement results. For each test, explain when presenting your work what it checks, why it is needed, and how it works.
- Do not add tests for logic outside the changes you are making. If you find testing gaps in adjacent logic, flag them for the maintainer to review instead.
- Expected values in tests must come from an independent source (hand calculation, a published reference, or another trusted tool), never from running the code under test. Say where each one came from when presenting your work.
- Never weaken, delete, or modify existing tests to make them pass. If a test seems wrong, stop and ask.
