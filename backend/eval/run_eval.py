#!/usr/bin/env python
"""Evaluate the three built-in demonstration scenarios against live pipeline output.

Run from the repository root:
    python backend/eval/run_eval.py

The checks inspect the actual answers, resolution status, preferred sources and
citations produced by the pipeline. Nothing is stubbed or pre-marked as passing.
If an LLM key is configured, the eval uses the real configured model path.
"""

from __future__ import annotations

import sys
import tempfile
import time
from datetime import date
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.config import Settings  # noqa: E402
from app.db import Database  # noqa: E402
from app.pipeline import run_query  # noqa: E402
from app.sample_corpus import DEMO_SCENARIOS, load_sample_corpus  # noqa: E402
from app.schemas import QueryResponse  # noqa: E402


def check_expense(result: QueryResponse) -> list[tuple[str, bool, str]]:
    titles = {citation.title for citation in result.citations}
    preferred = [
        conflict.preferred_document_title
        for conflict in result.conflicts
        if conflict.resolution == "resolved"
    ]
    return [
        ("status is resolved", result.status == "resolved", result.status),
        (
            "selects the amended ₹8,000 limit",
            "₹8,000" in result.answer,
            "found" if "₹8,000" in result.answer else "missing",
        ),
        (
            "prefers Finance Circular 2025-07",
            any(title and "Finance Circular 2025-07" in title for title in preferred),
            str(preferred),
        ),
        (
            "cites the superseded policy as well",
            "Finance & Expense Policy" in titles,
            str(sorted(titles)),
        ),
        ("structural validation passes", result.validation.valid, str(len(result.validation.checks))),
    ]


def check_leave(result: QueryResponse) -> list[tuple[str, bool, str]]:
    has_both_values = "12" in result.answer and "18" in result.answer
    preferred = [c.preferred_document_id for c in result.conflicts if c.resolution == "resolved"]
    return [
        (
            "status is conflict_unresolved",
            result.status == "conflict_unresolved",
            result.status,
        ),
        ("presents both 12 and 18 days", has_both_values, "both present" if has_both_values else "missing"),
        (
            "does not select a winner",
            not preferred,
            str(preferred),
        ),
        (
            "warns the FAQ does not establish authority",
            "informational" in result.resolution_reason.lower()
            or "authority" in result.resolution_reason.lower(),
            result.resolution_reason[:100],
        ),
        ("structural validation passes", result.validation.valid, str(len(result.validation.checks))),
    ]


def check_contractor(result: QueryResponse) -> list[tuple[str, bool, str]]:
    both_amounts = "₹50,000" in result.answer and "₹1,00,000" in result.answer
    preferred = [c.preferred_document_id for c in result.conflicts if c.resolution == "resolved"]
    return [
        (
            "status is conflict_unresolved",
            result.status == "conflict_unresolved",
            result.status,
        ),
        ("presents both thresholds", both_amounts, "both present" if both_amounts else "missing"),
        ("does not select a winner", not preferred, str(preferred)),
        (
            "answer explicitly abstains",
            "not claiming" in result.answer.lower()
            or "does not establish" in result.answer.lower(),
            result.answer[-120:],
        ),
        ("structural validation passes", result.validation.valid, str(len(result.validation.checks))),
    ]


CHECKERS = {
    "expense-amendment": check_expense,
    "leave-authority": check_leave,
    "contractor-threshold": check_contractor,
}


def main() -> int:
    settings = Settings.from_env()
    with tempfile.TemporaryDirectory(prefix="truthguard-eval-") as temp:
        db = Database(Path(temp) / "eval.db")
        db.init()
        load_sample_corpus(db)
        settings.db_path = db.path

        print("TruthGuard scenario evaluation")
        print(f"Mode: {settings.mode} ({settings.llm_model if settings.llm_configured else 'rules only'})")
        print(f"Sample documents: {len(db.list_documents())}")
        print("=" * 78)
        failures = 0
        total = 0
        for scenario in DEMO_SCENARIOS:
            started = time.perf_counter()
            result = run_query(
                db,
                settings,
                scenario.question,
                as_of=date.today(),
            )
            elapsed = time.perf_counter() - started
            checks = CHECKERS[scenario.id](result)
            total += len(checks)
            scenario_failed = [item for item in checks if not item[1]]
            failures += len(scenario_failed)
            status = "PASS" if not scenario_failed else "FAIL"
            print(f"\n[{status}] {scenario.label}")
            print(f"  expected: {scenario.expected_status} | actual: {result.status} | {elapsed * 1000:.0f} ms")
            print(f"  answer: {result.answer[:240].replace(chr(10), ' ')}")
            print(
                "  conflicts: "
                + (
                    ", ".join(
                        f"{conflict.kind}/{conflict.resolution}"
                        + (f" -> {conflict.preferred_document_title}" if conflict.preferred_document_title else "")
                        for conflict in result.conflicts
                    )
                    or "none"
                )
            )
            print(
                "  citations: "
                + (", ".join(f"{citation.title} v{citation.version} p.{citation.page}" for citation in result.citations) or "none")
            )
            for label, passed, detail in checks:
                print(f"    {'✓' if passed else '✗'} {label}: {detail}")

        print("\n" + "=" * 78)
        print(f"Result: {total - failures}/{total} checks passed across {len(DEMO_SCENARIOS)} scenarios.")
        if failures:
            print("Evaluation failed. Inspect the scenario details above.")
            return 1
        print("All demonstration scenarios produced the expected verified outcomes.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
