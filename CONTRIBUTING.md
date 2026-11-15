# Contributing

Read [AGENTS.md](AGENTS.md), [README.md](README.md) and [API_CONTRACT.md](API_CONTRACT.md) before changing interfaces. This repository contains Jose's local control, provider and optional voice lab. Its dispatcher runs simulations. An Intel mission service and physical robot integration remain separate work; a passing local test does not establish either.

## Set up and run checks

Use Python 3.12 and Node 24 on macOS or Linux. The Python source uses POSIX `fcntl`. From the repository root, install the existing pinned requirements:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r station/requirements.txt
```

Run the local lab suite and the voice JavaScript harness:

```bash
PYTHONPATH=station .venv/bin/python -m pytest station/tests -q -p no:cacheprovider
node station/tests/test_voice_browser.cjs
bash -n run.sh
MORPH_PYTHON="$PWD/.venv/bin/python" bash run.sh --help
```

The Node harness uses built-in modules and fake audio and sockets. It needs no npm installation, browser or microphone. It rewrites `station/verification/voice-browser-tests.json`; review the result before committing it, and retain the distinction between a new run and the original handoff evidence. The launcher help check exits without starting a service or creating runtime data.

Run the received Intel store/review tests in a separate Python process:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=intel-contract/source/station .venv/bin/python -m pytest \
  intel-contract/source/station/tests/test_store.py \
  intel-contract/source/station/tests/test_reviews.py \
  -q -p no:cacheprovider
```

The included Intel reference uses the same pinned requirements. Keep the two `PYTHONPATH` values separate: both trees define `morph_station`, and a recursive test invocation can import the wrong snapshot. These commands are local development checks; do not supply provider credentials or add live Intel, tunnel or robot actions to them. See [VERIFICATION.md](VERIFICATION.md) for the recorded results and their scope.

## Preserve source and evidence

Develop the runnable application in `station/`. Keep `intel-contract/source/` as the unchanged, read-only reference received from Intel on November 15, 2026. Its [manifest](intel-contract/manifest.json), [receipt](intel-contract/report.json) and [comparison](intel-contract/CONTRACT_COMPARISON.md) identify the received bytes. Do not replace the lab's models, store or API wholesale with that separate snapshot. If an agreed contract change requires adopting Intel behavior, make a focused application change with tests and describe the source used.

Preserve the original [Mac source manifest](SOURCE_MANIFEST.json) and Intel manifests. They identify historical snapshots, so later development should explain its divergence instead of rewriting those hashes to make changed files appear original. Retain existing dated verification artifacts; record new evidence with its actual timezone-qualified test time, command, source revision and outcome. Distinguish local simulation, provider testing, Intel-reported observations and independently verified physical behavior.

The saved [Intel audit runner](intel-contract/verification/run_reviewed_tests.py) is a historical artifact with canonical workspace paths. Do not run it unchanged from this clone. Use the standalone Intel test command above; the saved audit's network guards, generated schemas and zero-outbound result describe that original audited run, not every subsequent test invocation.

## Make focused changes

Keep project documentation in English. Use short, meaningful commits, each covering one coherent change and its relevant verification. Commit with the actual date of the work; put original source dates, transfer identifiers and attribution in the commit description when relevant. An import commit records an import and does not establish authorship or the original implementation date.

Keep credentials, local tokens, databases, recordings and private provider evidence out of Git. `env.example` contains optional variable names only and is not loaded automatically. The lab can start without provider keys. Inspect staged changes before committing, including generated test evidence.

Preserve the host boundaries in [THREE_HOST_ARCHITECTURE.md](THREE_HOST_ARCHITECTURE.md). Jose's future Intel mission client uses the NVIDIA tunnel supplied by the other team; this repository does not own tunnel configuration. Klemen communicates with Intel through the existing Mac MCP server. Opening, refreshing or reconnecting the interface must never initiate physical movement. Keep missing services and unverified outcomes explicit in code, documentation and reviews.
