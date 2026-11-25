"""Local browser UI: no Supabase, no Ollama, and no command line interaction."""
from __future__ import annotations

import csv
import io
import json
import os
from datetime import datetime
from urllib.parse import quote
from zoneinfo import ZoneInfo

import streamlit as st

import local_store
from claude_api import MODEL, ask_claude
from coach.roadmap import load_roadmap
from tracker_core import (OUTCOMES, daily_plan, due_reviews, legacy_import_payload,
                          review_date, solved_titles, streaks, topic_stats)

st.set_page_config(page_title="LeetCode Coach", page_icon="🧩", layout="wide")
st.markdown("""<style>
.block-container {max-width: 1100px; padding-top: 2rem}
[data-testid="stMetric"] {border:1px solid #d9e3ee;border-radius:12px;padding:12px}
</style>""", unsafe_allow_html=True)

roadmap = load_roadmap("neetcode-150")
today = datetime.now(ZoneInfo("America/Toronto")).date()
rows = local_store.attempts()
username = local_store.get_setting("leetcode_username")
profile = "https://leetcode.com/u/" + quote(username, safe="") + "/" if username else "https://leetcode.com/"

with st.sidebar:
    st.title("🧩 LeetCode Coach")
    st.caption("Local tracker · Claude optional")
    page = st.radio("Go to", ["Dashboard", "Practice", "History", "Settings"])
    st.link_button("Open my LeetCode ↗", profile)
    st.caption("Your practice notes stay on this computer. Claude receives only the data you send when you click Ask Claude.")


def problem_url(title: str) -> str:
    # Search is robust to LeetCode slugs that differ from the displayed title.
    return "https://leetcode.com/problemset/?search=" + quote(title)


def claude_key() -> str:
    return st.session_state.get("claude_key", "") or local_store.load_api_key() or os.getenv("ANTHROPIC_API_KEY", "")


if page == "Dashboard":
    st.title("Your coding practice")
    st.caption("NeetCode 150 · saved locally · open a problem on LeetCode and log your own result here")
    solved = solved_titles(rows)
    current, longest = streaks(rows, today)
    due = due_reviews(rows, today)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Solved", len(solved))
    c2.metric("Attempts", len(rows))
    c3.metric("Streak", f"{current} days")
    c4.metric("Reviews due", len(due))
    st.progress(len(solved) / len(roadmap.problems), text=f"Roadmap: {len(solved)} / {len(roadmap.problems)} solved")
    st.caption(f"Longest streak: {longest} days")

    left, right = st.columns([1.35, 1])
    with left:
        st.subheader("Today's practice")
        budget = st.slider("Time available (minutes)", 15, 120, 45, 15)
        suggestions = daily_plan(roadmap, rows, budget, today)
        for item in suggestions:
            with st.container(border=True):
                st.markdown(f"**{item['title']}** · {item['kind']}")
                st.caption(f"{item['topic']} · {item['difficulty']} · ~{item['minutes']} min")
                st.link_button("Solve on LeetCode ↗", problem_url(item["title"]))
        if not suggestions:
            st.info("No suitable problems for this time budget.")

        st.subheader("Ask Claude")
        st.caption(f"Optional personalized plan using {MODEL}. A call uses paid API credits.")
        if st.button("Explain my next practice plan", type="primary"):
            try:
                context = {"date": today.isoformat(), "time_budget_minutes": budget,
                           "suggestions": suggestions,
                           "recent_attempts": [dict(problem=r["problem_title"], date=r["practice_date"],
                                                    outcome=r["outcome"], notes=r["notes"]) for r in rows[:25]]}
                with st.spinner("Claude is thinking…"):
                    st.session_state.plan_answer = ask_claude(
                        claude_key(),
                        "In 150 words or fewer, recommend a practice order using the suggested titles only. Explain why based on the recent attempts. Do not invent progress.",
                        context)
            except (ValueError, RuntimeError) as exc:
                st.error(str(exc))
        if st.session_state.get("plan_answer"):
            st.info(st.session_state.plan_answer)

    with right:
        st.subheader("Progress by topic")
        for topic in topic_stats(roadmap, rows):
            st.progress(topic["solved"] / topic["total"],
                        text=f"{topic['topic']}: {topic['solved']}/{topic['total']}")

elif page == "Practice":
    st.title("Log a problem")
    st.caption("Solve it on LeetCode, then record what happened. This app never asks for your LeetCode password.")
    topic = st.selectbox("Topic", ["All topics"] + roadmap.topics())
    search = st.text_input("Find a problem", placeholder="Two Sum")
    matches = [p for p in roadmap.problems if (topic == "All topics" or p.topic == topic)
               and search.casefold().strip() in p.title.casefold()]
    if matches:
        title = st.selectbox("Problem", [p.title for p in matches])
        problem = roadmap.by_title(title)
        st.caption(f"{problem.topic} · {problem.difficulty}")
        st.link_button("Open problem on LeetCode ↗", problem_url(title))
        with st.form("save_attempt"):
            label = st.selectbox("Result", list(OUTCOMES))
            a, b = st.columns(2)
            day = a.date_input("Date", today, max_value=today)
            minutes = b.number_input("Minutes", 0, 1440, 20)
            notes = st.text_area("What did you learn or get stuck on?", max_chars=3000)
            submitted = st.form_submit_button("Save practice", type="primary")
        if submitted:
            outcome = OUTCOMES[label]
            local_store.save({"problem_title": title, "topic": problem.topic,
                              "difficulty": problem.difficulty, "practice_date": day.isoformat(),
                              "outcome": outcome, "minutes": int(minutes), "notes": notes.strip(),
                              "review_on": review_date(day, outcome)})
            st.success("Saved on this computer.")
            st.rerun()
    else:
        st.info("No matching problem in the NeetCode 150 roadmap.")

    st.divider()
    st.subheader("Review queue")
    if due_reviews(rows, today):
        for row in due_reviews(rows, today):
            st.markdown(f"**{row['problem_title']}** · due {row['review_on']}")
            st.link_button(f"Open {row['problem_title']} ↗", problem_url(row["problem_title"]))
    else:
        st.caption("All caught up.")

elif page == "History":
    st.title("Practice history")
    if rows:
        st.dataframe([{"Date": r["practice_date"], "Problem": r["problem_title"],
                       "Result": r["outcome"].replace("_", " "), "Minutes": r["minutes"],
                       "Notes": r["notes"]} for r in rows], hide_index=True, width="stretch")
        st.subheader("Ask Claude for feedback")
        focus = st.text_area("What would you like help with?", placeholder="What pattern am I struggling with, and what should I review next?")
        if st.button("Get feedback"):
            if not focus.strip():
                st.warning("Add a question first.")
            else:
                try:
                    context = {"recent_attempts": [dict(title=r["problem_title"], date=r["practice_date"],
                                    outcome=r["outcome"], notes=r["notes"]) for r in rows[:30]]}
                    with st.spinner("Claude is thinking…"):
                        st.session_state.feedback_answer = ask_claude(claude_key(), focus.strip(), context)
                except (ValueError, RuntimeError) as exc:
                    st.error(str(exc))
        if st.session_state.get("feedback_answer"):
            st.info(st.session_state.feedback_answer)
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=["practice_date", "problem_title", "topic", "difficulty", "outcome", "minutes", "notes", "review_on"])
        writer.writeheader()
        writer.writerows({k: r[k] for k in writer.fieldnames} for r in rows)
        st.download_button("Download CSV backup", output.getvalue().encode("utf-8-sig"), "practice-history.csv", "text/csv")
    else:
        st.info("Your saved practice sessions will appear here.")

elif page == "Settings":
    st.title("Connections & settings")
    st.subheader("LeetCode")
    name = st.text_input("LeetCode username", value=username, help="The name in your leetcode.com/u/username/ profile URL.")
    if st.button("Save LeetCode profile"):
        name = name.strip().strip("/")
        if name and (len(name) > 50 or not all(c.isalnum() or c in "_-" for c in name)):
            st.error("Enter only your profile username, using letters, numbers, underscores or hyphens.")
        else:
            local_store.set_setting("leetcode_username", name)
            st.rerun()
    st.caption("Profile and problem links only. LeetCode does not authorize this app to read your private submissions automatically.")

    st.subheader("Claude API")
    def save_key():
        try:
            local_store.save_api_key(st.session_state.get("claude_key", ""))
            st.session_state.claude_key = ""
            st.session_state.key_notice = "API key saved on this Mac. You won't need to paste it next time."
        except (OSError, ValueError) as exc:
            st.session_state.key_notice = f"Could not save key: {exc}"

    def forget_key():
        try:
            local_store.delete_api_key()
            st.session_state.claude_key = ""
            st.session_state.key_notice = "Saved API key removed from this Mac."
        except OSError as exc:
            st.session_state.key_notice = f"Could not remove key: {exc}"

    try:
        saved = bool(local_store.load_api_key())
    except OSError as exc:
        saved = False
        st.error(f"Could not read saved key: {exc}")
    st.caption("✅ A key is saved on this Mac" if saved else "No API key saved yet")
    st.text_input("Anthropic API key", type="password", key="claude_key",
                  placeholder="Paste a new key to save or replace the current one")
    a, b = st.columns(2)
    a.button("Save API key on this Mac", on_click=save_key)
    if saved:
        b.button("Forget saved key", on_click=forget_key)
    if st.session_state.get("key_notice"):
        st.info(st.session_state.pop("key_notice"))
    st.caption("Stored in a user-only local file outside Git, not in the practice database. Anyone with access to your Mac user account could read that file.")
    st.caption("An API key from the Anthropic Console is required. Claude Pro does not include API usage; some other plans may include API credits. Calls send your selected notes and attempt history to Anthropic.")

    st.subheader("Import your original CLI history")
    upload = st.file_uploader("Choose the old state.json file", type="json")
    if upload and st.button("Import attempts"):
        try:
            raw = json.load(upload)
            if not isinstance(raw, dict) or not isinstance(raw.get("records"), dict):
                raise ValueError("This does not look like a LeetCode Coach state.json file.")
            imported, skipped = legacy_import_payload(raw, roadmap, "local")
            count = local_store.import_legacy(imported)
            st.success(f"Imported {count} new attempts; {skipped} entries could not be matched. Reimporting will not duplicate them.")
        except (ValueError, TypeError, UnicodeDecodeError) as exc:
            st.error(f"Could not import file: {exc}")
