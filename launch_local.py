"""Started by the macOS app bundle; opens the private loopback browser UI."""
from __future__ import annotations

import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PORT = 18517
URL = f"http://127.0.0.1:{PORT}"


def ready() -> bool:
    try:
        with urllib.request.urlopen(URL + "/_stcore/health", timeout=0.5) as response:
            return response.status == 200
    except (urllib.error.URLError, TimeoutError):
        return False


if __name__ == "__main__":
    if not ready():
        log_dir = ROOT / ".local_data"
        log_dir.mkdir(exist_ok=True)
        with (log_dir / "launcher.log").open("a") as output:
            server = subprocess.Popen(
                [sys.executable, "-m", "streamlit", "run", str(ROOT / "local_app.py"),
                 "--server.address=127.0.0.1", f"--server.port={PORT}",
                 "--server.headless=true", "--browser.gatherUsageStats=false"],
                cwd=ROOT, stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        for _ in range(60):
            if ready():
                break
            if server.poll() is not None:
                break
            time.sleep(0.25)
    if ready():
        webbrowser.open(URL)
    else:
        error_page = ROOT / ".local_data" / "start_error.html"
        error_page.write_text("<h2>LeetCode Coach could not start</h2><p>Check launcher.log in the .local_data folder for details.</p>")
        webbrowser.open(error_page.as_uri())
