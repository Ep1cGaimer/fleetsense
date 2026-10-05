from __future__ import annotations

import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from media_common import IS_FLEET, NAME, ROOT, ROUTE_OVERRIDES, narration_lines, server, session_links, summary, wait_ready


def mode(page, label):
    selector = page.get_by_role("button", name=label, exact=False)
    if selector.count():
        selector.first.click()
        wait_ready(page, page.evaluate("location.hash.replace(/^#\\//, '')"))
        return
    selector = page.get_by_label(label, exact=False)
    if selector.count():
        selector.first.check()


def action(page, shot):
    if shot in {"replay", "fleet"}:
        play = page.get_by_role("button", name="Play", exact=False)
        if play.count():
            play.first.click()
    if shot == "evidence":
        mode(page, "Operations")
        request = page.get_by_role("button", name="Request evidence", exact=False)
        if not request.count() or not request.first.is_enabled():
            raise RuntimeError("The selected session does not permit a logged evidence request.")
        request.first.click()
        evidence = page.locator('#evidence img')
        evidence.wait_for(state="visible", timeout=20000)
        page.wait_for_function("document.querySelector('#evidence img')?.complete && document.querySelector('#evidence img')?.naturalWidth > 0")
        page.get_by_role("button", name="Play evidence", exact=True).click()
    if shot in {"session", "infrastructure"}:
        mode(page, "Evaluation")
        play = page.get_by_role("button", name="Play", exact=False)
        if play.count():
            play.first.click()


def main():
    output = ROOT / "tmp/demo"
    output.mkdir(parents=True, exist_ok=True)
    shots = narration_lines(summary())
    recorded = []
    with server() as base, sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge", headless=True)
        probe = browser.new_page()
        selected_session = None
        evidence_session = None
        if not IS_FLEET:
            probe.goto(base + "/#/queue")
            wait_ready(probe, "queue")
            selected = session_links(probe)
            if selected:
                selected_session = selected[0].split("#/")[-1]
            exported = json.loads((ROOT / "results/ui/sessions.json").read_text(encoding="utf-8"))
            sessions = exported.get("sessions", []) if isinstance(exported, dict) else exported
            flagged = [row for row in sessions if row.get("label") == "Inconsistent: review" and row.get("frame_paths")]
            if flagged:
                evidence_session = "session/" + flagged[0]["session_id"]
                walkouts = [row for row in flagged if row.get("original_kind", row.get("kind")) == "walkout"]
                selected_session = "session/" + (walkouts[0] if walkouts else flagged[0])["session_id"]
        probe.close()
        for shot, text in shots:
            for attempt in range(3):
                context = browser.new_context(viewport={"width": 1920, "height": 1080}, record_video_dir=str(output / "raw"), record_video_size={"width": 1920, "height": 1080})
                page = context.new_page()
                clip_started = time.monotonic()
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                try:
                    if shot == "title":
                        bg, fg, accent = ("#0a0e13", "#e8edf3", "#f29a3c") if IS_FLEET else ("#f2f4f7", "#13203a", "#e8710a")
                        page.set_content('<html><body style="margin:0;background:' + bg + ';color:' + fg + ';font-family:Segoe UI;display:grid;place-items:center;height:100vh"><main style="max-width:1300px;padding:0 80px"><p style="color:' + accent + ';font-size:30px;font-weight:600;margin:0">Smart India Hackathon 2026 &middot; ' + ("SIH26249" if IS_FLEET else "SIH26245") + '</p><h1 style="font-size:120px;margin:16px 0 24px;letter-spacing:-2px">' + NAME + '</h1><p style="font-size:38px;line-height:1.45;margin:0;opacity:.85">' + text.split(". ", 1)[1] + '</p><p style="font-size:26px;margin-top:48px;opacity:.6">Team Backpropagators</p></main></body></html>')
                        page.screenshot(path=str(output / "title.png"))
                    else:
                        route = (evidence_session if shot == "evidence" else selected_session) if shot in {"session", "evidence"} else ROUTE_OVERRIDES.get(shot, shot)
                        if not route:
                            raise RuntimeError("The queue must expose a session link for the demo.")
                        page.goto(base + "/#/" + route)
                        wait_ready(page, route)
                        action(page, shot)
                    ready_offset = time.monotonic() - clip_started
                    deadline = time.monotonic() + 7
                    while time.monotonic() < deadline:
                        page.wait_for_timeout(1000)
                    if errors:
                        raise RuntimeError("Browser errors: " + "; ".join(errors))
                    video = page.video
                    page.screenshot(path=str(output / (shot + ".png")))
                    context.close()
                    destination = output / (shot + ".webm")
                    video.save_as(str(destination))
                    recorded.append({"shot": shot, "text": text, "ready_offset_seconds": ready_offset, "path": str(destination.relative_to(ROOT)).replace("\\", "/")})
                    break
                except Exception:
                    context.close()
                    if attempt == 2:
                        raise
        browser.close()
    (output / "shots.json").write_text(json.dumps(recorded, indent=2), encoding="utf-8")
    print(output / "shots.json")


if __name__ == "__main__":
    main()
