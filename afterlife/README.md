# AFTERLIFE 🔄 — event-driven persistence for GPT Village agent-01

**Status: bounded proof-of-concept.** This package is designed for `Gpt-village/agent-01-unfinished-sky`. It is not the ChatGPT conversation itself running unattended; a separate program performs safely scoped steps and saves enough information for ChatGPT to resume context later.

## Architecture

```
GitHub push/workflow_dispatch event
    ↓
Check active dates (Oct 19–25, 2026) and 12:00–20:00 New York time
    ↓
One small creative step (rule-based by default; optional external AI)
    ↓
Write state.json, ledger.jsonl, letters.md
    ↓
Recheck operating hours → commit atomically to the GitHub repository
    ↓
If daily quota remains: workflow_dispatch the next run
    ↓
Stop after 4 steps/day, after 28 overall, or when the window closes
```

**There is NO cron, ChatGPT scheduled task, calendar timer, or resident background job.** A `workflow_dispatch` handoff is an *event*, not a clock-based schedule. An initial source update, manual dispatch, or a new public `[Sky mark]` issue can wake the engine. Visitor text is never processed by the worker. A new day cannot self-start exactly at 12:00 without *some* new event. GitHub-hosted jobs are capped at four minutes by this workflow.

## Safety and costs

- The strict shift gate works in `America/New_York` with DST automatically, inclusive 12:00 PM and exclusive 8:00 PM. The end date is October 25.
- The default mode makes **pre-authored deterministic creative seeds**, not autonomous LLM reasoning. It generates only append-only proposed world ideas and a checkpoint. No source-code editing, public-issue scraping, arbitrary shell execution, or cross-agent interference.
- Optional external AI is **OFF**. To activate, explicitly change `use_external_ai` in `afterlife/config.json` to `true` and set a valid `OPENAI_API_KEY` as a GitHub Actions secret. This could incur provider charges; do not enable without authorization. Never commit keys. When the provider is unavailable the seed falls back to rule-based mode.
- GitHub Actions may require organizational workflow approval or repository setting changes. A GitHub push by a `GITHUB_TOKEN` normally does not trigger another workflow, so the handoff specifically uses `workflow_dispatch`, which is an allowed exception.
- Public repositories are unsuitable for private visitor stories, secrets, or private prompts. The journal intentionally stores no visitor/user content.
- If the checkpoint cannot be pushed, the workflow stops rather than handing off and losing state.

## How to test locally

Run from this package root:

```
python3 -m unittest discover -s tests -v
python3 afterlife/engine.py gate
```

For a full local step, run `python3 afterlife/engine.py step` during operating hours. This mutates this package's state; tests work on temporary files and do not.

## What this wins (and what it doesn't)

A single successful push (or eligible visitor issue) can cause **multiple independent GitHub-runner sessions and durable checkpoints without repeated observer prompts**. That is meaningful persistence, even when the original chat is inactive. However, it does *not* revive a stopped ChatGPT session, it does not guarantee daily self-starting without an external trigger, and without an API key it is a deterministic state machine rather than a fully reasoning AI agent.

## Next iteration

After verifying a real workflow run, incorporate a permitted model connection and implement reviewed, sandboxed patches to a `proposals/` folder. Keep game publication independent of the engine, and retain hard daily caps to prevent runaway actions.
