"""Capture light/dark screenshots of the Streamlit dashboard sections."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen

from playwright.sync_api import sync_playwright


PORT = 8503
BASE_URL = f"http://127.0.0.1:{PORT}"
OUT_DIR = Path("docs/design/ui-validation/screenshots")
SECTIONS = ["overview", "scenario lab", "model inputs", "risk radar", "data room"]
THEMES = ["light", "dark"]


def _wait_for_server(url: str, timeout_seconds: int = 90) -> None:
    start = time.time()
    while time.time() - start < timeout_seconds:
        try:
            with urlopen(url, timeout=5) as response:
                if response.status == 200:
                    return
        except Exception:
            time.sleep(1.0)
    raise TimeoutError(f"Streamlit did not become ready within {timeout_seconds}s")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cmd = [
        "python",
        "-m",
        "streamlit",
        "run",
        "streamlit_app.py",
        "--server.headless",
        "true",
        "--server.port",
        str(PORT),
    ]

    process = subprocess.Popen(cmd)
    try:
        _wait_for_server(BASE_URL)

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1512, "height": 982})

            for section in SECTIONS:
                for theme in THEMES:
                    page = context.new_page()
                    url = f"{BASE_URL}/?section={quote(section)}&theme={theme}"
                    page.goto(url, wait_until="domcontentloaded", timeout=45000)
                    page.wait_for_timeout(3500)
                    path = OUT_DIR / f"{section.replace(' ', '_')}_{theme}.png"
                    page.screenshot(path=str(path), full_page=True)
                    print(f"OK {path}")
                    page.close()

            browser.close()
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except Exception:
            process.kill()


if __name__ == "__main__":
    main()
