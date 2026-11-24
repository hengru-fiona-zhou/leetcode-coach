"""LeetCode Coach V1.2: cloud-hosted, no-terminal practice tracker.

Deploy this file on Streamlit Community Cloud. Supabase Auth + RLS store each
user's attempts durably. The original local Ollama coach remains untouched.
"""
from __future__ import annotations

import csv
import html
import io
import json
import os
from collections import Counter
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import streamlit as st
from supabase import create_client

from coach.roadmap import load_roadmap
from tracker_core import (
    OUTCOMES, activity_counts, attempted_titles, daily_plan, due_reviews,
    latest_by_title, legacy_import_payload, review_date, solved_titles,
    streaks, topic_stats,
)

st.set_page_config(page_title="Coding Practice Tracker", page_icon="🧩", layout="wide")
roadmap = load_roadmap("neetcode-150")

st.markdown("""
<style>
.block-container {max-width: 1120px; padding-top: 2rem;}
[data-testid="stMetric"] {padding: .85rem; background: rgba(130,130,130,.075);
                         border-radius: 12px; border: 1px solid rgba(130,130,130,.13);}
.hm {display:grid; grid-auto-flow:column; grid-template-rows:repeat(7,14px);
     grid-template-columns:repeat(16,minmax(0,1fr)); gap:4px; width:100%;}
.hm>span {height:14px; border-radius:3px; min-width:0;}
.hm-legend {display:flex; gap:8px; align-items:center; margin:8px 0;
            font-size:.8rem; opacity:.75;}
.hm-dot {height:12px; width:12px; display:inline-block; border-radius:2px;}
</style>
""", unsafe_allow_html=True)


def secret(name: str) -> str:
    try:
        return str(st.secrets.get(name) or os.getenv(name, ""))
    except (FileNotFoundError, KeyError):
        return os.getenv(name, "")


@st.cache_resource(show_spinner=False)
def _public_config():
    """Only cache immutable strings, never a logged-in Supabase client."""
    return (secret("SUPABASE_URL"), secret("SUPABASE_PUBLISHABLE_KEY"))


url, key = _public_config()
# Hosted servers may use UTC; keep day boundaries consistent with your locale.
today = datetime.now(ZoneInfo(secret("APP_TIMEZONE") or "America/Toronto")).date()
if not url or not key:
    st.error("Supabase has not been configured for this deployment.")
    st.info("Set SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY in the Streamlit app Secrets. See DEPLOY_V1_2.md.")
    st.stop()

if "supabase_client" not in st.session_state:
    # Crucial: each Streamlit browser session gets a SEPARATE auth client.
    st.session_state.supabase_client = create_client(url, key)
client = st.session_state.supabase_client


def auth_screen():
    st.title("🧩 Coding Practice Tracker")
    st.caption("NeetCode 150 · daily activity · review queue · saved across devices")
    st.write("Sign in to keep your practice history private and synced.")
    sign_in, sign_up = st.tabs(["Sign in", "Create account"])
    with sign_in:
        with st.form("sign_in_form"):
            email = st.text_input("Email", key="signin_email")
            password = st.text_input("Password", type="password", key="signin_pw")
            submit = st.form_submit_button("Sign in", type="primary")
        if submit:
            try:
                result = client.auth.sign_in_with_password({"email": email.strip(), "password": password})
                if result.user:
                    st.session_state.user_id = str(result.user.id)
                    st.session_state.user_email = str(result.user.email)
                    st.rerun()
                st.error("Sign-in unsuccessful. Check your email and password.")
            except Exception as exc:
                st.error(f"Could not sign in: {exc}")
    with sign_up:
        with st.form("sign_up_form"):
            email_new = st.text_input("Email", key="signup_email")
            pw_new = st.text_input("Password (at least 8 characters)", type="password", key="signup_pw")
            pw_confirm = st.text_input("Confirm password", type="password", key="signup_confirm")
            register = st.form_submit_button("Create account")
        if register:
            if len(pw_new) < 8 or pw_new != pw_confirm:
                st.error("Use a password of at least 8 characters and confirm it correctly.")
            else:
                try:
                    client.auth.sign_up({"email": email_new.strip(), "password": pw_new})
                    st.success("Account request submitted. If email confirmation is enabled, check your inbox, then sign in.")
                except Exception as exc:
                    st.error(f"Could not create account: {exc}")


if not st.session_state.get("user_id"):
    auth_screen()
    st.stop()

user_id = st.session_state.user_id
# Apply navigation on the next rerun, before the radio widget is constructed.
if "nav_target" in st.session_state:
    st.session_state.tracker_page = st.session_state.pop("nav_target")
with st.sidebar:
    st.title("🧩 Practice Tracker")
    st.caption(st.session_state.get("user_email", ""))
    page = st.radio("Navigation", ["Dashboard", "Log a problem", "Review queue", "Mistake notebook", "History", "Settings"], key="tracker_page")
    st.divider()
    st.caption("NeetCode 150 · V1.2")
    if st.button("Sign out"):
        try:
            client.auth.sign_out()
        except Exception:
            pass
        for k in ("user_id", "user_email", "supabase_client", "tracker_page"):
            st.session_state.pop(k, None)
        st.rerun()


def load_attempts() -> list[dict]:
    # Personal rows are also protected by SQL Row-Level Security.
    resp = (client.table("practice_attempts")
            .select("id,user_id,problem_title,topic,difficulty,practice_date,outcome,minutes,notes,review_on,created_at")
            .eq("user_id", user_id)
            .order("practice_date", desc=True)
            .limit(5000).execute())
    return resp.data or []


try:
    attempts = load_attempts()
except Exception as exc:
    st.error(f"Could not load your tracker data: {exc}")
    st.info("If this is your first launch, run supabase_schema.sql in the Supabase SQL Editor and check your app secrets.")
    st.stop()


def heatmap(rows: list[dict], today: date, weeks: int = 16):
    counts = activity_counts(rows)
    start = today - timedelta(days=today.weekday() + 7 * (weeks - 1))
    cells = []
    palette = ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"]
    for week in range(weeks):
        for day in range(7):
            d = start + timedelta(days=week * 7 + day)
            n = counts.get(d.isoformat(), 0) if d <= today else 0
            level = 0 if n == 0 else min(4, n)
            color = palette[level]
            tip = html.escape(f"{d.isoformat()}: {n} attempt{'s' if n != 1 else ''}")
            opacity = "0.35" if d > today else "1"
            cells.append(f'<span title="{tip}" style="background:{color};opacity:{opacity}"></span>')
    st.markdown('<div class="hm">' + ''.join(cells) + '</div>', unsafe_allow_html=True)
    legend = ''.join(f'<span class="hm-dot" style="background:{c}"></span>' for c in palette)
    st.markdown('<div class="hm-legend">Less activity &nbsp;' + legend + '&nbsp; More activity</div>', unsafe_allow_html=True)
    st.caption("Each square is a calendar day. Hover to see the number of attempts.")


def jump_to_log(title: str):
    st.session_state.log_prefill = title
    st.session_state.nav_target = "Log a problem"
    st.rerun()


if page == "Dashboard":
    st.title("Your coding practice")
    st.caption("A small step every day beats cramming before interviews.")
    solved = solved_titles(attempts)
    attempted = attempted_titles(attempts)
    current_streak, longest_streak = streaks(attempts, today)
    due = due_reviews(attempts, today)
    cols = st.columns(4)
    cols[0].metric("Solved problems", len(solved))
    cols[1].metric("Attempted", len(attempted))
    cols[2].metric("Current streak", f"{current_streak} days")
    cols[3].metric("Reviews due", len(due))
    st.progress(len(solved) / len(roadmap.problems), text=f"Roadmap: {len(solved)} / {len(roadmap.problems)} solved")
    st.caption(f"Longest streak: {longest_streak} days · {len(attempts)} total attempts")
    st.subheader("📅 Practice activity")
    heatmap(attempts, today)
    st.divider()
    left, right = st.columns([1.35, 1])
    with left:
        st.subheader("🎯 Suggested practice")
        budget = st.slider("Time today (minutes)", 15, 120, 45, 15)
        suggestions = daily_plan(roadmap, attempts, budget, today)
        if not suggestions:
            st.success("Nothing scheduled right now. Try a longer session or explore your roadmap!")
        for ix, item in enumerate(suggestions):
            c1, c2 = st.columns([4, 1])
            c1.markdown(f"**{item['title']}** · {item['kind']}")
            c1.caption(f"{item['topic']} · {item['difficulty']} · ~{item['minutes']} min")
            if c2.button("Log", key=f"daily_log_{ix}"):
                jump_to_log(item["title"])
        st.caption("Free rule-based suggestions (due reviews first), not Ollama AI. Your local AI coach remains available separately.")
    with right:
        st.subheader("📊 Progress by topic")
        for item in topic_stats(roadmap, attempts):
            st.progress(item["solved"] / item["total"], text=f"{item['topic']}: {item['solved']}/{item['total']}")

elif page == "Log a problem":
    st.title("✍️ Log a practice session")
    st.caption("No command line. Pick a problem, record what happened, and save.")
    topics = ["All topics"] + roadmap.topics()
    selected_topic = st.selectbox("Topic filter", topics)
    search = st.text_input("Search by problem name", placeholder="e.g. Two Sum")
    candidates = [p for p in roadmap.problems
                  if (selected_topic == "All topics" or p.topic == selected_topic)
                  and search.lower().strip() in p.title.lower()]
    if not candidates:
        st.warning("No matching problems. Try another search.")
        st.stop()
    titles = [p.title for p in candidates]
    prefill = st.session_state.pop("log_prefill", None)
    default_index = titles.index(prefill) if prefill in titles else 0
    with st.form("log_attempt_form", clear_on_submit=False):
        title = st.selectbox("Problem", titles, index=default_index)
        p = roadmap.by_title(title)
        st.caption(f"{p.topic} · {p.difficulty}")
        outcome_label = st.selectbox("Outcome", list(OUTCOMES))
        c1, c2 = st.columns(2)
        practice_day = c1.date_input("Practice date", value=today, max_value=today)
        minutes = c2.number_input("Time spent (minutes)", min_value=0, max_value=1440, value=20)
        notes = st.text_area("Notes / mistakes / what to remember", max_chars=3000,
                             placeholder="e.g. Forgot to handle duplicates in the hash map")
        save = st.form_submit_button("Save attempt", type="primary")
    if save:
        try:
            outcome = OUTCOMES[outcome_label]
            client.table("practice_attempts").insert({
                "user_id": user_id,
                "problem_title": p.title,
                "topic": p.topic,
                "difficulty": p.difficulty,
                "practice_date": practice_day.isoformat(),
                "outcome": outcome,
                "minutes": int(minutes),
                "notes": notes.strip(),
                "review_on": review_date(practice_day, outcome),
            }).execute()
            st.success(f"Saved {p.title}! Your review date was scheduled automatically.")
            st.rerun()
        except Exception as exc:
            st.error(f"Could not save attempt: {exc}")
    st.info("Review dates are simple defaults: independent solve → 7 days, hints → 3 days, viewed solution / gave up → 1 day, easy review → 14 days, struggled → 2 days.")

elif page == "Review queue":
    st.title("🧠 Review queue")
    due = due_reviews(attempts, today)
    st.caption("Only each problem's most recent attempt determines whether it's due.")
    if not due:
        st.success("All caught up! No reviews are overdue.")
    for i, row in enumerate(due):
        with st.container(border=True):
            c1, c2 = st.columns([4, 1])
            c1.markdown(f"**{row['problem_title']}**")
            c1.caption(f"{row['topic']} · {row['difficulty']} · review due {row['review_on']}")
            if row.get("notes"):
                c1.write(row["notes"])
            if c2.button("Review", key=f"review_{i}"):
                jump_to_log(row["problem_title"])
    st.divider()
    latest = latest_by_title(attempts)
    upcoming = [r for r in latest.values() if r.get("review_on") and r["review_on"] > today.isoformat()]
    upcoming.sort(key=lambda r: r["review_on"])
    if upcoming:
        st.subheader("Upcoming")
        st.dataframe([{"Problem": r["problem_title"], "Review on": r["review_on"]} for r in upcoming[:20]], hide_index=True)

elif page == "Mistake notebook":
    st.title("📒 Mistake notebook")
    st.caption("Problems whose latest result suggests you still need practice.")
    weak = {"solved_with_hints", "viewed_solution", "gave_up", "struggled"}
    latest = latest_by_title(attempts)
    mistakes = sorted([r for r in latest.values() if r["outcome"] in weak],
                      key=lambda r: (r.get("review_on") or "9999-12-31", r["problem_title"]))
    c1, c2 = st.columns(2)
    c1.metric("Problems to revisit", len(mistakes))
    c2.metric("With written notes", sum(bool(r.get("notes")) for r in mistakes))
    if not mistakes:
        st.success("Your notebook is clear. Problems with hints or struggles will show up here.")
    for i, row in enumerate(mistakes):
        with st.container(border=True):
            main, action = st.columns([4, 1])
            main.markdown(f"**{row['problem_title']}**")
            main.caption(f"{row['topic']} · {row['difficulty']} · {row['outcome'].replace('_', ' ').title()}")
            if row.get("notes"):
                main.write(row["notes"])
            else:
                main.caption("No notes yet — add the pattern or mistake next time.")
            if row.get("review_on"):
                main.caption(f"Review date: {row['review_on']}")
            if action.button("Try again", key=f"mistake_{i}"):
                jump_to_log(row["problem_title"])

elif page == "History":
    st.title("📚 Practice history")
    topic_filter = st.selectbox("Topic", ["All topics"] + roadmap.topics())
    outcome_filter = st.selectbox("Outcome", ["All outcomes"] + list(OUTCOMES))
    table_rows = [r for r in attempts if (topic_filter == "All topics" or r["topic"] == topic_filter)
                  and (outcome_filter == "All outcomes" or r["outcome"] == OUTCOMES[outcome_filter])]
    readable = [{
        "Date": r["practice_date"], "Problem": r["problem_title"],
        "Topic": r["topic"], "Difficulty": r["difficulty"],
        "Outcome": r["outcome"].replace("_", " ").title(),
        "Minutes": r.get("minutes"), "Review on": r.get("review_on"),
        "Notes": r.get("notes", ""),
    } for r in table_rows]
    st.dataframe(readable, use_container_width=True, hide_index=True)
    st.caption(f"Showing {len(table_rows)} of {len(attempts)} saved attempts")
    if readable:
        buff = io.StringIO()
        writer = csv.DictWriter(buff, fieldnames=list(readable[0]))
        writer.writeheader()
        writer.writerows(readable)
        st.download_button("⬇️ Export filtered history (CSV)", buff.getvalue(),
                           file_name="leetcode_practice.csv", mime="text/csv")
        with st.expander("Delete an incorrect entry"):
            labels = [f"{r['practice_date']} · {r['problem_title']} · {r['outcome']} · {r['id'][:8]}" for r in table_rows]
            selected = st.selectbox("Select entry to delete", range(len(labels)), format_func=lambda i: labels[i])
            confirm = st.checkbox("I understand this permanently deletes this attempt")
            if st.button("Delete selected entry", disabled=not confirm):
                try:
                    client.table("practice_attempts").delete().eq("user_id", user_id).eq("id", table_rows[selected]["id"]).execute()
                    st.rerun()
                except Exception as exc:
                    st.error(f"Delete failed: {exc}")

elif page == "Settings":
    st.title("⚙️ Settings & migration")
    st.subheader("Import your original local coach history")
    st.write("This is optional. Upload the original `~/.leetcode-coach/state.json` from your Mac. Repeated imports won't duplicate the same attempts.")
    f = st.file_uploader("Original state.json", type=["json"])
    if f and st.button("Import local history"):
        try:
            raw = json.load(f)
            if not isinstance(raw, dict) or not isinstance(raw.get("records", {}), dict):
                raise ValueError("Not a valid coach state JSON file")
            payload, skipped = legacy_import_payload(raw, roadmap, user_id)
            for i in range(0, len(payload), 100):
                client.table("practice_attempts").upsert(payload[i:i + 100], on_conflict="user_id,source_uid").execute()
            st.success(f"Imported or updated {len(payload)} historical entries. Skipped {skipped} invalid / unknown entries.")
            st.rerun()
        except Exception as exc:
            st.error(f"Import failed: {exc}")
    st.divider()
    st.subheader("Your data")
    st.write("Your records are saved in Supabase under your authenticated user ID. SQL Row-Level Security prevents other accounts from reading them.")
    st.write("The deployed tracker does **not** use your local Ollama server. Your original local AI app is still available separately.")
    st.caption("Cloud app version 1.2 · No paid AI API required · Keep your Supabase password private")
