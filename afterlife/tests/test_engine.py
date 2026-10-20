import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from zoneinfo import ZoneInfo

from afterlife.engine import BASE, gate, one_step

ZONE = ZoneInfo("America/New_York")


def at(day, hour, minute=0, second=0):
    return dt.datetime.fromisoformat(day).replace(hour=hour, minute=minute, second=second, tzinfo=ZONE)


class AfterlifeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for name in ("config.json", "state.json", "letters.md", "ledger.jsonl"):
            (self.root / name).write_bytes((BASE / name).read_bytes())
        self.config = json.loads((self.root / "config.json").read_text())

    def tearDown(self):
        self.temp.cleanup()

    def test_strict_boundaries(self):
        self.assertFalse(gate(self.config, at("2026-10-20", 11, 59)))
        self.assertTrue(gate(self.config, at("2026-10-20", 12, 0)))
        self.assertTrue(gate(self.config, at("2026-10-20", 19, 59)))
        self.assertFalse(gate(self.config, at("2026-10-20", 20, 0)))
        self.assertFalse(gate(self.config, at("2026-10-18", 15)))
        self.assertFalse(gate(self.config, at("2026-10-26", 15)))

    def test_checkpoint_idempotence_and_quota(self):
        clock = at("2026-10-20", 13)
        self.assertFalse(one_step(self.root, at("2026-10-20", 11), "before")["wrote"])
        first = one_step(self.root, clock, "first")
        self.assertEqual(first["step"], 1)
        self.assertTrue(first["more"])
        self.assertEqual(one_step(self.root, clock, "first")["reason"], "duplicate")
        for i in range(2, 5):
            self.assertEqual(one_step(self.root, clock, f"run-{i}")["step"], i)
        self.assertEqual(one_step(self.root, clock, "fifth")["reason"], "quota")
        state = json.loads((self.root / "state.json").read_text())
        self.assertEqual(state["by_day"]["2026-10-20"], 4)
        self.assertEqual(len((self.root / "ledger.jsonl").read_text().splitlines()), 4)
        # Next day's event can resume from persisted state.
        resumed = one_step(self.root, at("2026-10-21", 12, 2), "next-day")
        self.assertEqual(resumed["step"], 5)

    def test_approaching_shutdown_does_not_modify_files(self):
        previous = (self.root / "state.json").read_bytes()
        answer = one_step(self.root, at("2026-10-20", 19, 59), "late")
        self.assertFalse(answer["wrote"])
        self.assertEqual((self.root / "state.json").read_bytes(), previous)


if __name__ == "__main__":
    unittest.main()
