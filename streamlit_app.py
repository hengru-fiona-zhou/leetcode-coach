
from datetime import date, timedelta

import streamlit as st
from coach.coach import Coach
from coach.store import Store
from coach.cli import _load_plan, _save_plan

st.set_page_config(
    page_title="LeetCode Coach",
    page_icon="🧠",
    layout="wide",
)

store = Store()
coach = Coach(store=store)

st.title("🧠 LeetCode Coach")
st.caption("Your personal coding interview tracker · Powered by local AI")

# First-time setup
if not coach.is_initialized():
    st.info("Let's initialize your roadmap first.")
    if st.button("Start NeetCode 150"):
        coach.initialize("neetcode-150")
        st.rerun()
    st.stop()

progress = coach.progress()
state = store.load()

attempts = [
    {
        "Date": a.date,
        "Problem": rec.title,
        "Outcome": a.outcome.replace("_", " ").title(),
        "Minutes": a.minutes,
    }
    for rec in state.records.values()
    for a in rec.attempts
]

active_days = len({
    a["Date"] for a in attempts
    if a["Date"] >= (date.today() - timedelta(days=6)).isoformat()
})

# Dashboard
st.subheader("Dashboard")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Solved", progress["solved"])
c2.metric("Attempted", progress["attempted"])
c3.metric("Reviews Due", progress["due_reviews"])
c4.metric("Active Days (7d)", active_days)

total = progress["total"]
percent = progress["solved"] / total if total else 0
st.progress(percent, text=f"Roadmap completion: {percent:.1%}")

st.divider()

# AI daily planning
st.subheader("✨ Your AI Practice Plan")

minutes = st.slider(
    "How much time do you have today?",
    min_value=15,
    max_value=180,
    value=45,
    step=15,
)

if st.button("Generate Practice Plan", type="primary"):
    try:
        with st.spinner("Your local AI is preparing your plan..."):
            new_plan = coach.plan_today(minutes)
            _save_plan(store, new_plan)
        st.rerun()
    except Exception as exc:
        st.error(f"Could not generate plan: {exc}")

plan = _load_plan(store)

if plan:
    st.caption("Most recently generated plan")
    if plan.coach_note:
        st.info(plan.coach_note)

    for item in plan.items:
        with st.container(border=True):
            st.markdown(f"**{item.title}** · {item.kind.upper()}")
            st.caption(
                f"{item.topic} · {item.difficulty} "
                f"· {item.estimated_minutes} min"
            )
            if item.reason:
                st.write(item.reason)
else:
    st.info("Generate your first practice plan above.")

st.divider()

# Practice feedback
st.subheader("📝 Log Your Practice")

last_result = st.session_state.pop("last_feedback", None)
if last_result:
    st.success(f"Saved {len(last_result.get('applied', []))} problem updates.")
    if last_result.get("coach_note"):
        st.info(last_result["coach_note"])
    if last_result.get("unmatched"):
        st.warning(f"Unmatched: {last_result['unmatched']}")

with st.form("feedback_form"):
    feedback = st.text_area(
        "How did your session go?",
        placeholder=(
            "I solved Two Sum in 10 minutes without hints. "
            "Group Anagrams took 25 minutes and I needed one hint."
        ),
        height=120,
    )
    submitted = st.form_submit_button("Save Session")

if submitted:
    if not feedback.strip():
        st.warning("Please enter your practice feedback.")
    else:
        try:
            with st.spinner("Updating your learning history..."):
                result = coach.record_feedback(
                    feedback.strip(), plan=plan
                )
            st.session_state["last_feedback"] = result
            st.rerun()
        except Exception as exc:
            st.error(f"Could not save feedback: {exc}")

st.divider()

# Topic progress
st.subheader("📊 Progress by Topic")
with st.expander("View all topics", expanded=True):
    for topic in progress["by_topic"]:
        if topic["total"]:
            ratio = topic["solved"] / topic["total"]
            st.progress(
                ratio,
                text=f"{topic['topic']}: "
                     f"{topic['solved']}/{topic['total']}",
            )

# Recent attempts
st.subheader("📚 Practice History")
if attempts:
    attempts.sort(key=lambda x: x["Date"], reverse=True)
    st.dataframe(
        attempts[:30],
        hide_index=True,
        use_container_width=True,
    )
else:
    st.info("Your practice history will appear here.")
