from pathlib import Path

from playwright.sync_api import sync_playwright

from media_common import ROOT, ROUTES, server, wait_ready


def main():
    output = ROOT / "submission/assets"
    output.mkdir(parents=True, exist_ok=True)
    with server() as base, sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page(viewport={"width": 1600, "height": 1000}, device_scale_factor=2)
        for route in ROUTES:
            page.goto(base + "/#/" + route)
            wait_ready(page, route)
            page.screenshot(path=str(output / ("shot_" + route + ".png")), full_page=False)
        browser.close()
    print(output)


if __name__ == "__main__":
    main()
