"""Optional Claude API calls; credentials never leave the local Python process except to Anthropic."""
from __future__ import annotations

import json
import urllib.error
import urllib.request

MODEL = "claude-sonnet-4-6"
ENDPOINT = "https://api.anthropic.com/v1/messages"


def ask_claude(api_key: str, instruction: str, context: dict) -> str:
    if not api_key.strip():
        raise ValueError("Add your Claude API key in Settings first.")
    payload = {
        "model": MODEL,
        "max_tokens": 1000,
        "system": "You are a practical coding interview coach. Use only the supplied practice data. Be concise, specific, and honest. Do not claim access to a user's LeetCode account or submitted code.",
        "messages": [{"role": "user", "content": instruction + "\n\nPractice data:\n" + json.dumps(context, ensure_ascii=False)}],
    }
    request = urllib.request.Request(
        ENDPOINT, data=json.dumps(payload).encode(), method="POST",
        headers={"Content-Type": "application/json", "x-api-key": api_key.strip(),
                 "anthropic-version": "2023-06-01"},
    )
    try:
        with urllib.request.urlopen(request, timeout=75) as response:
            result = json.load(response)
    except urllib.error.HTTPError as exc:
        # Do not display a raw response or API key in the UI.
        descriptions = {400: "Request rejected", 401: "Invalid API key", 402: "API billing is unavailable",
                        403: "API key lacks access", 429: "Rate limit reached"}
        raise RuntimeError(f"Claude: {descriptions.get(exc.code, 'HTTP error')} ({exc.code}).") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError("Claude is unreachable. Check your internet connection.") from exc
    blocks = result.get("content", [])
    answer = "\n".join(block.get("text", "") for block in blocks if block.get("type") == "text").strip()
    if not answer:
        raise RuntimeError("Claude returned no text.")
    return answer
