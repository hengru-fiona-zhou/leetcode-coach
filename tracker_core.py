"""Pure V1.2 tracker logic, deliberately independent of Streamlit and Ollama."""
from __future__ import annotations

from collections import Counter
from datetime import date, timedelta
from hashlib import sha256
from typing import Any, Iterable

SOLVED = {"solved_independently", "solved_with_hints", "reviewed_easily"}
OUTCOMES = {
    "Solved independently": "solved_independently",
    "Solved with hints": "solved_with_hints",
    "Viewed solution": "viewed_solution",
    "Gave up": "gave_up",
    "Reviewed easily": "reviewed_easily",
    "Struggled": "struggled",
}
REVIEW_INTERVAL_DAYS = {
    "solved_independently": 7,
    "solved_with_hints": 3,
    "viewed_solution": 1,
    "gave_up": 1,
    "reviewed_easily": 14,
    "struggled": 2,
}


def review_date(practice_day: date, outcome: str) -> str:
    return (practice_day + timedelta(days=REVIEW_INTERVAL_DAYS[outcome])).isoformat()


def attempted_titles(rows: Iterable[dict[str, Any]]) -> set[str]:
    return {r["problem_title"] for r in rows}


def solved_titles(rows: Iterable[dict[str, Any]]) -> set[str]:
    return {r["problem_title"] for r in rows if r["outcome"] in SOLVED}


def activity_counts(rows: Iterable[dict[str, Any]]) -> Counter[str]:
    return Counter(r["practice_date"] for r in rows)


def streaks(rows: Iterable[dict[str, Any]], today: date | None = None) -> tuple[int, int]:
    """Return current streak and longest streak; yesterday may anchor current streak."""
    today = today or date.today()
    days = {date.fromisoformat(r["practice_date"]) for r in rows}
    days = {day for day in days if day <= today}
    if not days:
        return 0, 0
    start = today if today in days else today - timedelta(days=1)
    current = 0
    while start in days:
        current += 1
        start -= timedelta(days=1)
    best = running = 0
    previous = None
    for day in sorted(days):
        running = running + 1 if previous and day == previous + timedelta(days=1) else 1
        best = max(best, running)
        previous = day
    return current, best


def latest_by_title(rows: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest = {}
    for row in sorted(rows, key=lambda r: (r["practice_date"], r.get("created_at", ""))):
        latest[row["problem_title"]] = row
    return latest


def due_reviews(rows: Iterable[dict[str, Any]], today: date | None = None) -> list[dict[str, Any]]:
    today = today or date.today()
    latest = latest_by_title(rows)
    return sorted(
        [r for r in latest.values() if r.get("review_on") and r["review_on"] <= today.isoformat()],
        key=lambda r: (r["review_on"], r["problem_title"]),
    )


def topic_stats(roadmap: Any, rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    solved = solved_titles(rows)
    result = []
    for topic in roadmap.topics():
        problems = [p for p in roadmap.problems if p.topic == topic]
        result.append({"topic": topic, "total": len(problems), "solved": sum(p.title in solved for p in problems)})
    return result


def daily_plan(roadmap: Any, rows: list[dict[str, Any]], minutes: int, today: date | None = None) -> list[dict[str, Any]]:
    """Offline heuristic, NOT AI: due reviews first, then new problems in roadmap order."""
    today = today or date.today()
    seen = attempted_titles(rows)
    chosen = []
    remaining = minutes
    for r in due_reviews(rows, today):
        p = roadmap.by_title(r["problem_title"])
        if p is None:
            continue
        estimate = 8 if p.difficulty.lower() == "easy" else 12
        if estimate <= remaining:
            chosen.append({"title": p.title, "topic": p.topic, "difficulty": p.difficulty, "minutes": estimate, "kind": "Review"})
            remaining -= estimate
    for p in roadmap.problems:
        if p.title in seen:
            continue
        estimate = {"easy": 15, "medium": 25, "hard": 40}.get(p.difficulty.lower(), 25)
        if estimate <= remaining:
            chosen.append({"title": p.title, "topic": p.topic, "difficulty": p.difficulty, "minutes": estimate, "kind": "New"})
            remaining -= estimate
        if remaining < 8:
            break
    return chosen


def legacy_import_payload(raw: dict[str, Any], roadmap: Any, user_id: str) -> tuple[list[dict[str, Any]], int]:
    """Map the original ~/.leetcode-coach/state.json into cloud attempt rows.

    Stable source_uid makes repeated imports idempotent with the SQL unique constraint.
    """
    output = []
    skipped = 0
    for title, record in raw.get("records", {}).items():
        p = roadmap.by_title(title)
        if p is None:
            skipped += 1
            continue
        entries = record.get("attempts", [])
        for index, attempt in enumerate(entries):
            outcome = attempt.get("outcome")
            if outcome not in REVIEW_INTERVAL_DAYS:
                skipped += 1
                continue
            try:
                practice_day = date.fromisoformat(attempt["date"])
            except (KeyError, TypeError, ValueError):
                skipped += 1
                continue
            minutes = attempt.get("minutes")
            if not isinstance(minutes, int) or isinstance(minutes, bool) or minutes < 0:
                minutes = None
            # Attach old next_review only to that title's latest imported attempt.
            review_on = record.get("next_review") if index == len(entries) - 1 else None
            if review_on:
                try:
                    date.fromisoformat(review_on)
                except (ValueError, TypeError):
                    review_on = None
            signature = sha256(f"legacy|{title}|{index}|{attempt['date']}".encode()).hexdigest()
            output.append({
                "user_id": user_id,
                "source_uid": signature,
                "problem_title": title,
                "topic": p.topic,
                "difficulty": p.difficulty,
                "practice_date": practice_day.isoformat(),
                "outcome": outcome,
                "minutes": minutes,
                "notes": str(attempt.get("notes") or "")[:3000],
                "review_on": review_on,
            })
    return output, skipped
