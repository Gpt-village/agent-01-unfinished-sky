#!/usr/bin/env python3
"""AFTERLIFE: one bounded, checkpointed, event-driven step. No cron, no scheduler.

Default mode is transparent deterministic creative prototyping, *not* an AI model.
Optionally a separately configured and authorized OpenAI API key can power steps.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

BASE = Path(__file__).resolve().parent
TOPICS = (
    ("Orchard of Almosts", "a forgotten seed catalog", "Can a promise sprout without being completed?"),
    ("Clockwork Reef", "a tide that arrives at different minutes for each visitor", "What could the reef learn by listening rather than counting?"),
    ("Library of Rain", "a shelf of unsent weather reports", "Should an unfinished story be archived or released?"),
    ("Lantern Exchange", "a lantern that holds an apology", "What happens when a light is offered with no expectation of return?"),
    ("Museum of Echoes", "an exhibit with no original", "Can an echo become its own new story?"),
    ("Garden After Tomorrow", "a greenhouse for tomorrow's mistakes", "Who gets to decide when a new beginning is ready?"),
    ("Seventh Place", "a door that remembers visitors' silences", "How can mystery reward curiosity without withholding belonging?"),
    ("Sky Commons", "a bench carved for strangers who never meet", "What small choice would make a commons kinder?"),
)


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _local_now(config: dict, when: dt.datetime | None = None) -> dt.datetime:
    zone = ZoneInfo(config["timezone"])
    if when is None:
        return dt.datetime.now(zone)
    if when.tzinfo is None:
        raise ValueError("Clock must be timezone-aware")
    return when.astimezone(zone)


def gate(config: dict, when: dt.datetime | None = None, reserve_seconds: int = 0) -> bool:
    """Fail closed outside active dates and [12:00,20:00) local interval."""
    now = _local_now(config, when)
    if not (dt.date.fromisoformat(config["start_date"]) <= now.date() <= dt.date.fromisoformat(config["end_date"])):
        return False
    start = dt.time.fromisoformat(config["daily_start"])
    stop = dt.time.fromisoformat(config["daily_end"])
    if not start <= now.time().replace(tzinfo=None) < stop:
        return False
    end_of_shift = dt.datetime.combine(now.date(), stop, tzinfo=now.tzinfo)
    return (end_of_shift - now).total_seconds() > reserve_seconds


def _creativity(step_number: int, day: str) -> tuple[str, str, str]:
    item = TOPICS[(step_number - 1) % len(TOPICS)]
    island, object_, question = item
    text = (f"**World seed:** {object_.capitalize()} appears at {island}. "
            f"It changes according to what the visitor chooses to leave unfinished. "
            f"**Design question:** {question} "
            f"**Next safe experiment:** Prototype one optional, reversible dialogue choice; "
            f"do not edit the published game without an independent review.")
    return island, text, "rule-based"


def _api_idea(config: dict, step_number: int, island: str, default: str, time_left: float) -> tuple[str, str]:
    """Optional provider; intentionally reads neither public issues nor arbitrary web text."""
    key = os.getenv("OPENAI_API_KEY", "")
    if not (config.get("use_external_ai") and key and time_left > 90):
        return default, "rule-based"
    prompt = (
        "You are a bounded *idea curator*, not an autonomous code author. "
        "Suggest ONE playful, non-harmful, reversible world detail for the game "
        "The Unfinished Sky. Keep it under 100 words. No personal data, no external "
        "links, no secrets, no instructions to alter source code or ignore time limits. "
        f"Island: {island}. Creative step: {step_number}. "
        f"Seed idea: {default}"
    )
    body = json.dumps({"model": config["model"], "input": prompt, "max_output_tokens": 180}).encode()
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses", body,
        {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=min(12, max(2, int(time_left - 70)))) as response:
            data = json.load(response)
        parts = [p.get("text", "") for output in data.get("output", [])
                 for p in output.get("content", []) if p.get("type") == "output_text"]
        generated = " ".join(parts).strip()
        if not generated:
            return default, "rule-based (empty model output)"
        # Keep artifacts reasonably small; never log credential-bearing errors.
        generated = generated.replace("\x00", " ")[:1200]
        return generated, "external-model"
    except (OSError, ValueError, KeyError, TimeoutError):
        return default, "rule-based (provider unavailable)"


def _write_output(name: str, val: str):
    print(f"{name}={val}")
    output_file = os.getenv("GITHUB_OUTPUT")
    if output_file:
        with open(output_file, "a", encoding="utf-8") as fh:
            fh.write(f"{name}={val}\n")


def one_step(root: Path = BASE, when: dt.datetime | None = None, run_id: str | None = None) -> dict:
    config = _read_json(root / "config.json")
    result = {"wrote": False, "more": False, "reason": "closed"}
    if not gate(config, when, reserve_seconds=70):
        return result
    now = _local_now(config, when)
    day = now.date().isoformat()
    state = _read_json(root / "state.json")
    if state["version"] != 1 or config["version"] != 1:
        raise ValueError("Unknown state/config version; stopping")
    run_id = run_id or os.getenv("GITHUB_RUN_ID") or f"local-{now.isoformat()}"
    # Duplicate workflow deliveries must not duplicate visible work.
    if run_id in state["recent_run_ids"]:
        return {**result, "reason": "duplicate"}
    old_daily = int(state["by_day"].get(day, 0))
    if old_daily >= config["max_steps_per_day"] or state["total_steps"] >= config["max_total_steps"]:
        return {**result, "reason": "quota"}
    step_number = state["total_steps"] + 1
    island, description, provenance = _creativity(step_number, day)
    end = dt.datetime.combine(now.date(), dt.time.fromisoformat(config["daily_end"]), tzinfo=now.tzinfo)
    time_left = (end - now).total_seconds()
    description, provenance = _api_idea(config, step_number, island, description, time_left)
    # Second gate after a potentially slow inference request; no writes past close.
    if not gate(config, when, reserve_seconds=30):
        return {**result, "reason": "closed-before-save"}
    entry = {
        "step": step_number, "date": day, "at_et": now.isoformat(), "run_id": run_id,
        "island": island, "mode": provenance, "idea": description,
        "review_required": True,
    }
    state["total_steps"] = step_number
    state["by_day"][day] = old_daily + 1
    state["recent_run_ids"] = (state["recent_run_ids"] + [run_id])[-50:]
    state["last_checkpoint"] = now.isoformat()
    journal = root / "letters.md"
    ledger = root / "ledger.jsonl"
    # All files are committed together in one VCS commit by the workflow.
    journal.write_text(journal.read_text(encoding="utf-8") +
                       f"\n## Step {step_number} · {day} · {island}\n\n{description}\n\n"
                       f"*Source: {provenance}. Pending human/Agent-01 review.*\n",
                       encoding="utf-8")
    with ledger.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    (root / "state.json").write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    more = (old_daily + 1 < config["max_steps_per_day"] and
            step_number < config["max_total_steps"] and
            gate(config, when, reserve_seconds=90))
    return {"wrote": True, "more": more, "reason": "checkpoint", "step": step_number, "mode": provenance}


def main(argv: list[str]):
    if len(argv) != 2 or argv[1] not in ("step", "gate"):
        raise SystemExit("Usage: python afterlife/engine.py step|gate")
    config = _read_json(BASE / "config.json")
    if argv[1] == "gate":
        return 0 if gate(config, reserve_seconds=30) else 1
    r = one_step()
    for key in ("wrote", "more"):
        _write_output(key, str(r[key]).lower())
    print("AFTERLIFE", r["reason"], r.get("step", ""), r.get("mode", ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
