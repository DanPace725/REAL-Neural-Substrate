from __future__ import annotations

import json
import shutil
import unittest
from pathlib import Path

from scripts.generate_trace_index import build_index, parse_trace, write_index


class TestGenerateTraceIndex(unittest.TestCase):
    def setUp(self) -> None:
        self.trace_root = Path("tests_tmp") / "trace_index"
        if self.trace_root.exists():
            shutil.rmtree(self.trace_root)
        self.trace_root.mkdir(parents=True)

        (self.trace_root / "2026-03-19 1151 - Session Synthesis Anticipation.md").write_text(
            "\n".join(
                [
                    "# 2026-03-19 1151 - Session Synthesis Anticipation",
                    "",
                    "**Type:** Session synthesis  ",
                    "**Model:** GPT-5 Codex  ",
                    "",
                    "Touched `real_core/engine.py`, `phase8/selector.py`, and [expectation.py](C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/phase8/expectation.py).",
                    "",
                    "Anticipation, prediction, and carryover all mattered here.",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        (self.trace_root / "20260317_phase8_neural_baseline_trace.md").write_text(
            "\n".join(
                [
                    "# Phase 8 Neural Baseline Trace",
                    "",
                    "Author: GPT-5.2-Codex",
                    "",
                    "Compared `scripts/neural_baseline.py` against `phase8/node_agent.py`.",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        if self.trace_root.exists():
            shutil.rmtree(self.trace_root)

    def test_parse_trace_extracts_metadata_and_paths(self) -> None:
        path = self.trace_root / "2026-03-19 1151 - Session Synthesis Anticipation.md"
        entry = parse_trace(path, self.trace_root)

        self.assertEqual(entry.trace_type, "Session synthesis")
        self.assertEqual(entry.model, "GPT-5 Codex")
        self.assertEqual(entry.timestamp, "2026-03-19T11:51")
        self.assertIn("real_core/engine.py", entry.referenced_files)
        self.assertIn("phase8/expectation.py", entry.referenced_files)
        self.assertIn("anticipation", entry.keywords)
        self.assertIn("selector", entry.keywords)

    def test_build_index_creates_keyword_and_file_maps(self) -> None:
        index = build_index(self.trace_root)

        self.assertEqual(index["entry_count"], 2)
        self.assertIn("anticipation", index["by_keyword"])
        self.assertIn("phase8/selector.py", index["by_file"])

    def test_write_index_emits_json_and_markdown(self) -> None:
        json_output = self.trace_root / "index.json"
        md_output = self.trace_root / "INDEX.md"

        write_index(
            self.trace_root,
            json_output=json_output,
            markdown_output=md_output,
        )

        self.assertTrue(json_output.exists())
        self.assertTrue(md_output.exists())
        payload = json.loads(json_output.read_text(encoding="utf-8"))
        markdown = md_output.read_text(encoding="utf-8")
        self.assertEqual(payload["entry_count"], 2)
        self.assertIn("# Trace Index", markdown)
        self.assertIn("Top Keywords", markdown)


if __name__ == "__main__":
    unittest.main()
