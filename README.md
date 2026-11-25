# AI Daily LeetCode Coach

## Local browser app (macOS)

Double-click **LeetCode Coach.app** in this folder. It opens a private browser page at `http://127.0.0.1:18517` without asking you to type Terminal commands. Keep this folder in place: the launcher refers to this local checkout and uses the existing Python environment installed on this Mac. Closing the browser tab does not erase your history; you can open the app again at any time.

The local app saves practice history in `.local_data/practice.sqlite3` (excluded from Git). Its Settings page lets you add your LeetCode **username** for profile links and opens individual problems on LeetCode. Your LeetCode submissions are **not automatically synced**; log your result in the app after solving. No LeetCode password or browser cookie is requested. You can import the old CLI `state.json` in Settings and download a CSV backup from History.

For optional AI planning and feedback, paste an **Anthropic API key** in Settings and click **Save API key on this Mac**. The app remembers it in a user-only local file (`.local_data/claude_api_key`, mode 0600) that Git ignores; use **Forget saved key** to remove it. This is a plain-text file readable by your Mac user account, not an encrypted Keychain item. Only the context shown by this app is sent when you click a Claude button. Claude Pro does not include API usage; some other plans may include API credits. The tracker works without an API key and never calls Ollama.

The previously deployed `cloud_app.py` is separate and continues to use Supabase. It does not automatically share history with this local app.

## Original command-line app

This fork replaces the original Claude API integration with a locally hosted Qwen model through Ollama. It allows users to generate personalized LeetCode practice plans and track their progress without paid API access.

An AI coach that decides exactly what you should practice each day. Not a
tracker, not a dashboard — a coach. You only ever do two things:

1. Tell it how much time you have today.
2. Tell it (in plain English) how the session went.

The AI owns everything else: where you are on the roadmap, what to introduce
next, what to review, and when each problem should come back.

See [VISION.md](VISION.md) for the long-term product vision and how today's MVP
maps to it.

```
$ leetcode-coach plan 45

Today's a mix: two fresh Arrays & Hashing problems plus a quick review of
Two Sum to keep it warm.

Focus: a mix of new & review

  1. Two Sum  [review]
     Arrays & Hashing · Easy · ~8 min
     You solved this last week — a fast refresh before building on it.
  2. Group Anagrams  [new]
     Arrays & Hashing · Medium · ~22 min
     Next in your roadmap; builds directly on hashing patterns.
  ...

$ leetcode-coach done "Group Anagrams took me 25 min, needed one hint on the
  sorting key. Two Sum was instant."

Recorded:
  ✓ Group Anagrams  (solved with hints)   → review around 2026-07-14
  ✓ Two Sum  (reviewed easily)            → review around 2026-08-16

Nice — the hint on Group Anagrams was just the key-choice; the pattern itself
clearly landed. I'll surface it again in a couple of days to lock it in.
```

## How it works

- **Curriculum** — a fixed roadmap (NeetCode 150 in the MVP): topic order and
  candidate problems. The coach always knows where you are and what's next.
- **Scheduler** — Claude decides your daily plan from your history and today's
  available time, balancing new material against due reviews.
- **Memory** — every attempt, outcome, hint, and review date is stored as plain
  JSON and updated automatically from your natural-language feedback. You never
  edit it by hand.

The intelligence (planning + reading your feedback) runs through Claude with
structured outputs; the record it maintains is clean JSON so future features
(analytics, dashboards, custom roadmaps) build on the same foundation.

## Install

```bash
pip install -e .
```

Set your Anthropic API key (or use the `ant` CLI login):

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

## Use

```bash
leetcode-coach init            # choose a roadmap (once)
leetcode-coach plan 45         # "I have 45 minutes" -> today's plan
leetcode-coach done "..."      # recap your session in plain English
leetcode-coach progress        # a quick look at where you are
```

`plan` accepts natural phrasings too: `plan "1 hour"`, `plan 90m`.

If you don't want to install, run it as a module: `python -m coach plan 45`.

Your history lives at `~/.leetcode-coach/state.json` (override with
`LEETCODE_COACH_HOME` or `--state`).

## Roadmap (beyond the MVP)

The architecture is built to grow into the full vision without a redesign:
personalized mistake analysis, concept-level mastery, adaptive spaced
repetition, interview-deadline plans, multiple/custom roadmaps, and a richer
dashboard. All of it builds on the same core idea — the AI observes your
history, knows where you are, and decides what you practice next.
