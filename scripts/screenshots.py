"""Take the README screenshots from a running demo (python demo.py).  Needs playwright and Edge."""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

EDGE = r"C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
OUT = Path(__file__).resolve().parent.parent / "docs" / "screenshots"
URL = "http://127.0.0.1:5000/"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=EDGE)
        d = b.new_page(viewport={"width": 1440, "height": 900})
        m = b.new_page(viewport={"width": 390, "height": 844})
        d.goto(URL); m.goto(URL)
        d.wait_for_selector("#watch li", timeout=60000)
        d.wait_for_timeout(1500)
        d.screenshot(path=str(OUT / "1-countdown-1440.png"))
        d.wait_for_selector("#banner:not([hidden])", timeout=60000)
        d.wait_for_timeout(1500)
        d.screenshot(path=str(OUT / "2-alert-1440.png"))
        m.wait_for_timeout(1500)
        m.screenshot(path=str(OUT / "5-alert-390.png"), full_page=True)
        print("390 scrollWidth", m.evaluate("document.documentElement.scrollWidth"))
        d.click("#banner-open")
        d.wait_for_timeout(3500)
        d.screenshot(path=str(OUT / "3-alert-detail-1440.png"))
        d.click("#d-raw-btn"); d.wait_for_timeout(1500)
        d.screenshot(path=str(OUT / "4-raw-footage-1440.png"))
        m.click("#banner-open"); m.wait_for_timeout(2500)
        m.screenshot(path=str(OUT / "6-alert-detail-390.png"))
        print("390 scrollWidth open", m.evaluate("document.documentElement.scrollWidth"))
        d.click("#d-close")
        d.wait_for_selector("#banner.escalated", timeout=90000)
        d.wait_for_timeout(1000)
        d.screenshot(path=str(OUT / "7-escalated-1440.png"))
        b.close()


if __name__ == "__main__":
    sys.exit(main())
