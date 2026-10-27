# Matches

Plan for the Matches tool. Not yet implemented.

## Runs

A run is one experiment under one spec. It plays a saved, ordered list of openings with a baseline build and a candidate build. The `mode` field sets who they play: `stockfish` (each build plays a strength-limited Stockfish) or `head-to-head` (the candidate plays the baseline build directly). It has two stages: an A/A stage that checks the harness, then an A/B stage that makes the comparison.

- A run uses the first N openings of a saved list, in list order. Lists are chosen with a recorded seed and never modified.
- If a crash occurs, the run stops. Step Functions cancels the jobs already running. A cancelled job writes no results, because jobs write only when they finish. No new jobs start.
- Each opening is played with both colors in each match. With `mode = "stockfish"` there are two matches, so 4 games per opening. With `mode = "head-to-head"` there is one match, so 2 games per opening.
- Time control is set per run. The default is 10+0.1.
- Runs are started manually.
- Each run has one run ID, from its spec. Every game records its stage, `aa` or `ab`.

### Run spec

A run is started from one TOML spec, and it has its own run ID. Specs are committed under `runs/`. Only one run executes at a time. Starting a run while another is active is refused.

```toml
mode = "stockfish"               # "stockfish" or "head-to-head". Sets who plays whom in every game of the run.
time_control = "10+0.1"
harness = "v1.8.2-alpha"         # fastchess version. Must match the version in the image.
openings_per_job = 32            # J. N and the A/A count must be multiples of J.
concurrency_per_job = 8          # games in flight per job, split evenly across the job's matches. Each game uses 2 vCPUs, so 8 fills a 16-vCPU instance.
max_instances = 2               # concurrent instances. 2 × 16 = 32 vCPUs, the current quota.
instance_type = "c6i.4xlarge"
region = "us-east-1"

[baseline]
branch = "main"                  # default
commit = "<full hash>"           # optional. If omitted, the head of the branch, resolved and recorded at run start.

[candidate]
branch = "<branch name>"
commit = "<full hash>"

[openings]
list_id = "<saved list id>"          # must already exist. Openings are used in list order.
count = 512                      # N, for the A/B stage

[aa]
count = 64                       # for the A/A stage. Omitted or 0 means no A/A stage, in either mode.

[stockfish]                      # read only when mode = "stockfish". Must be absent when mode = "head-to-head".
version = "<version>"
elo = 0
hash_mb = 0
threads = 1
```

Validation rules are listed in [Acceptance criteria](#acceptance-criteria).

### Stages

1. **A/A stage:** the baseline build plays itself on the first `[aa] count` openings of the `[openings]` list. With `stockfish`, each copy plays Stockfish. With `head-to-head`, both copies play each other in one match (self-play). Those are the same openings the A/B stage starts with.
2. **A/B stage:** with `stockfish`, the baseline and candidate builds each play Stockfish on the first `[openings] count` openings of the list. With `head-to-head`, the candidate plays the baseline build in one match on those openings.

The A/B stage starts automatically when the A/A stage finishes. If a crash stops the run, the A/B stage does not start.

Each run is one AWS Step Functions execution. It runs the stages in order, submits each job to Batch, and waits for it to finish. Runs are submitted with the submission CLI (see [Submission CLI](#submission-cli)). If a job fails, Step Functions cancels the jobs still running, no new jobs start, and the run is recorded as stopped.

## Submission CLI

The submission CLI is `submit_run.py`. It is a Python command that starts a run from a TOML spec. It uses only the Python standard library.

- Reads the spec with `tomllib` and checks it against the acceptance criteria. If a check fails, nothing is started.
- Converts the spec to JSON and starts the Step Functions execution with `aws stepfunctions start-execution`, called through `subprocess`.
- Needs an active AWS session. The operator runs `aws login` first. The CLI checks the session with `aws sts get-caller-identity` and stops with a clear message if there is none.
- Requires Python 3.14.

The loading CLI, which puts results into MySQL, is deferred.

## Jobs

A job plays J openings on one instance. With `stockfish`, the instance runs two matches at once, one for baseline and one for candidate, each with half of `concurrency_per_job` games in flight. The job ends when both finish, and baseline and candidate are paired by opening ID afterward. With `head-to-head`, the instance runs one match, the candidate against the baseline, with all of `concurrency_per_job` games in flight. Either way, the job uses all vCPUs of the instance.

A job writes its results only when it finishes, so a job can be discarded and rerun without leaving partial data. This keeps Spot instances possible later.

### Container

- The toolchain image holds gcc (to compile Springer), fastchess (the runner), and Stockfish. It's stored in Amazon ECR, a private AWS image registry.
- The base image, fastchess, and Stockfish are pinned: the base image by digest, and fastchess and Stockfish by the SHA-256 of their downloads. Stockfish is `sf_19`.
- Each job fetches the commit named in the spec and compiles it inside the container. The compile flags are fixed in the image.
- Jobs start from AWS Batch's default image, with no custom AMI. The toolchain image is pulled from ECR at job start.
- Each job records the SHA-256 of each compiled binary.

## Matches

A match is one invocation of the tool. With `stockfish`, it is one engine under test against Stockfish. With `head-to-head`, it is the candidate against the baseline build. It plays both colors of each of the job's openings, with its share of `concurrency_per_job` games running at once.

The runner is fastchess, version `v1.8.2-alpha`. It is pinned in the container image and recorded in the spec's `harness` field.

With `stockfish`, the two matches in a job are not synchronized, so at any moment they may be on different openings. The tool uses some CPU of its own. `-show-latency` reports each engine's latency, which shows how much of that overhead falls on each one.


## Recorded per run

- Run spec, run ID, start and end timestamps, location (`aws`), and status: completed, or stopped with the crash that caused it and the jobs that never started.
- Instance type, region, AMI ID, container image digest, and CPU model for each job.
- Branch, and the full commit hash each build came from, for baseline and candidate.
- Opening count for each stage, opening list ID, and seed.
- Mode (`stockfish` or `head-to-head`).
- Stockfish version, Elo, and settings, for `stockfish` runs only.
- Time control, harness version, openings per job (J), and concurrency per job.
- For each game: stage, opening, color, engine, result, plies, and how it ended.
- For each game and engine: total nodes and average nodes per second.
- For each engine in each job: latency mean and maximum from `-show-latency`.
- For each job: seconds from instance start to the first game, split into image pull and Springer compile.
- SHA-256 checksum of the full per-game data.

## Storage

- Per-game data goes to an S3 bucket with versioning on. Each job writes once, at the end, under the run's path, in one folder per stage (`aa`, `ab`).
- The aggregation step loads the run into a local MySQL database. MySQL data is not committed.
- Job logs go to CloudWatch Logs and are kept for 30 days.

## Infrastructure

AWS CDK defines the AWS resources, written in TypeScript. The maintainer confirmed CDK as the infrastructure tool. The CDK packages (`aws-cdk`, `aws-cdk-lib`, `constructs`) are approved. The Matches CDK app lives in `infra/matches/`, separate from the future Positions app. Each app has its own `cdk.json` and stacks, and the two share no buckets or roles. Batch jobs run in the default VPC's subnets, with a dedicated security group that has no inbound rules.

## Acceptance criteria

The tool rejects a spec when:

- A commit is not a full hash.
- `mode` is not `stockfish` or `head-to-head`.
- `mode` is `stockfish` and `[stockfish]` is missing, or `mode` is `head-to-head` and `[stockfish]` is present.
- `openings_per_job` does not divide N, or does not divide the A/A count when it is nonzero.
- N or the A/A count is larger than the saved list, or the A/A count is larger than N.
- `concurrency_per_job` × 2 does not equal the vCPUs of `instance_type`, so each job uses the whole instance.
- `mode` is `stockfish` and `concurrency_per_job` is odd, so it cannot split evenly across the two matches.
- `max_instances` × the vCPUs of `instance_type` is larger than the On-Demand vCPU quota.
- Stockfish `threads` is not 1 (`stockfish` runs only).

The tool:

- Uses the baseline build for both engines in the A/A stage, so build differences cannot appear as a result.
- Runs one job per instance. Each job requests all vCPUs of its instance, so Batch places one job on each.
- Limits the compute environment to `instance_type`, with a vCPU cap of `max_instances` × vCPUs.
- Does not pin engines to CPU cores.
- Records instance type, time control, harness version, mode, and concurrency per job for every run. Runs are comparable only when these match.

## Analysis (deferred)

The analysis method is decided after the tools are built and real runs have produced data. Until then, runs record what any analysis will need: job and opening IDs for pairing, and the CPU model for each job.

## Open items

**Decide before the first real run**

- Stockfish Elo and hash size, for `stockfish` runs. The spec has placeholders, and the reference harness used 16 MB.
- The opening list. See [matches_openings.md](matches_openings.md).
- The On-Demand vCPU quota in the chosen region. The spec assumes 32 vCPUs.

**Operator, before any AWS resources are created**

- Approve Step Functions, its IAM role, and the ECR repository.
- Create the S3 bucket with versioning and encryption, and no lifecycle deletion.
- Set a budget alarm.

**After the first real run**

- Whether 8 games in flight per job holds, using the A/A stage's latency data.
- Whether a pre-built AMI is worth it, using the recorded setup times.
- The analysis method.

**Deferred**

- Notifications when a run finishes or a job fails. This needs SNS or EventBridge, a new service.