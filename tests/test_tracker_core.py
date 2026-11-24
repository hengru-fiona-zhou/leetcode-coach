from dataclasses import dataclass
from datetime import date

from tracker_core import (
    daily_plan, due_reviews, legacy_import_payload, review_date,
    solved_titles, streaks, topic_stats,
)


@dataclass
class Problem:
    title: str
    topic: str
    difficulty: str


class Roadmap:
    problems = [Problem("Two Sum", "Arrays & Hashing", "Easy"),
                Problem("Group Anagrams", "Arrays & Hashing", "Medium"),
                Problem("Valid Parentheses", "Stack", "Easy")]

    def by_title(self, title):
        return next((p for p in self.problems if p.title == title), None)

    def topics(self):
        return ["Arrays & Hashing", "Stack"]


def row(title, day, outcome="solved_independently", review_on=None):
    return {"problem_title": title, "practice_date": day, "outcome": outcome,
            "review_on": review_on, "created_at": "2026-11-23T12:00:00Z"}


def test_streaks_and_solved_counts():
    history = [row("Two Sum", "2026-11-21"), row("Two Sum", "2026-11-22"),
               row("Group Anagrams", "2026-11-23", "viewed_solution")]
    assert streaks(history, date(2026, 11, 23)) == (3, 3)
    assert solved_titles(history) == {"Two Sum"}


def test_due_only_latest_attempt():
    history = [row("Two Sum", "2026-11-20", review_on="2026-11-22"),
               row("Two Sum", "2026-11-23", review_on="2026-11-30"),
               row("Group Anagrams", "2026-11-21", review_on="2026-11-22")]
    due = due_reviews(history, date(2026, 11, 23))
    assert [r["problem_title"] for r in due] == ["Group Anagrams"]


def test_rule_based_plan_and_stats():
    history = [row("Two Sum", "2026-11-20", review_on="2026-11-22")]
    plan = daily_plan(Roadmap(), history, 45, date(2026, 11, 23))
    assert [p["title"] for p in plan] == ["Two Sum", "Group Anagrams"]
    assert sum(p["minutes"] for p in plan) <= 45
    assert topic_stats(Roadmap(), history)[0]["solved"] == 1
    assert review_date(date(2026, 11, 23), "solved_with_hints") == "2026-11-26"


def test_legacy_import_stable_identifiers():
    old = {"records": {"Two Sum": {"title": "Two Sum", "topic": "Arrays & Hashing",
              "next_review": "2026-12-01", "attempts": [{"date": "2026-11-23",
              "outcome": "solved_independently", "minutes": 10}]}}}
    first, skipped = legacy_import_payload(old, Roadmap(), "user-a")
    second, _ = legacy_import_payload(old, Roadmap(), "user-a")
    assert skipped == 0
    assert first == second
    assert first[0]["review_on"] == "2026-12-01"
