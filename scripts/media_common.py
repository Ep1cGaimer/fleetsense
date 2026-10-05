from __future__ import annotations

import contextlib
import json
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IS_FLEET = (ROOT / "fleetsense").is_dir()
PORT = 8601 if IS_FLEET else 8602
PS = "SIH26249" if IS_FLEET else "SIH26245"
NAME = "FleetSense" if IS_FLEET else "CentreSight"
BASE_URL = "http://127.0.0.1:" + str(PORT)
ROUTES = ["fleet", "engine", "policies", "calibration", "audits"] if IS_FLEET else ["queue", "insufficient", "infrastructure", "sync", "results"]
ROUTE_OVERRIDES = {"engine": "engine/E00009"}


def summary():
    return json.loads((ROOT / "results/summary.json").read_text(encoding="utf-8-sig"))


def is_available():
    try:
        with urllib.request.urlopen(BASE_URL, timeout=1) as response:
            return response.status == 200
    except OSError:
        return False


@contextlib.contextmanager
def server():
    process = None
    stream = None
    if not is_available():
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", PORT)) == 0:
                raise RuntimeError("The dashboard port is occupied by a different service.")
        logs = ROOT / "tmp/media"
        logs.mkdir(parents=True, exist_ok=True)
        stream = (logs / "server.log").open("w", encoding="utf-8")
        module = "app.server:app" if IS_FLEET else "server.app:app"
        process = subprocess.Popen([sys.executable, "-m", "uvicorn", module, "--host", "127.0.0.1", "--port", str(PORT)], cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
        deadline = time.monotonic() + 45
        while not is_available():
            if process.poll() is not None or time.monotonic() > deadline:
                stream.flush()
                raise RuntimeError("Dashboard did not start. Inspect tmp/media/server.log.")
            time.sleep(.2)
    try:
        yield BASE_URL
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        if stream is not None:
            stream.close()


def wait_ready(page, route):
    page.wait_for_selector('body[data-ready="' + route.split("/")[0] + '"]', timeout=20000)
    page.evaluate("document.fonts.ready")


def session_links(page):
    return page.locator('a[href*="#/session/"]').evaluate_all("elements => elements.map(element => element.getAttribute('href'))")


def narration_lines(result):
    if IS_FLEET:
        missed = result["calibration"]["missed_warnings"]
        warned = (missed["assessable"] - missed["missed"]) / missed["assessable"] * 100
        counts = result["counts"]
        runs = counts["policy_runs"] + counts["bootstrap_policy_runs"] + counts["frontier_policy_runs"]
        waste = (1 - result["guardrails"]["wasted_life"]["ratio"]) * 100
        big = result["audits"]["scale"][-1]
        return [
            ("title", NAME + ". Fleet readiness and predictive maintenance for an air squadron, running entirely on base servers."),
            ("fleet", "The fleet board shows every airframe, its installed engine, and the calibrated risk that the engine fails within its next twenty cycles. Playing the year replays every removal request, engine change and overhaul, with spare engines tracked on the shelf."),
            ("engine", "Each engine's sensor trend is compared with healthy engines at the same age, and its failure risk is shown across planning horizons against the removal threshold."),
            ("policies", f"The policy lab runs fixed-interval, condition-based and predictive maintenance against the same simulated squadron. Predictive removal gave the highest availability and left {waste:.0f} percent less engine life on the table. The lab also shows when spare-engine supply, not forecasting, sets the ceiling."),
            ("calibration", f"Model trust checks that a risk score means what it says, on engines the model never saw. {warned:.1f} percent of failures were flagged before they happened."),
            ("audits", f"Every schedule is re-checked by an independent rule engine: {result['checker_violations']} violations across {runs:,} simulated squadron-years. {big['aircraft']} airframes simulate a full year in {big['wall_seconds']:.2f} seconds."),
        ]
    sync = result["sync"]
    ms = result["latency"]["cpu_ms_per_frame_960"]
    return [
        ("title", NAME + ". Attendance and equipment monitoring for skill training centres, on the CCTV they already have."),
        ("queue", "The review queue compares each session's head count with the attendance the centre reported, and ranks sessions by how likely they are over-reported."),
        ("session", "In a session, the dark line is trainees seen every ten seconds, the band is the likely range, and the dashed line is reported attendance. The camera replay shows the count with faces blurred."),
        ("evidence", "Footage never leaves the centre by default. A reviewer can request a short, face-blurred clip for a flagged session, and every request is logged."),
        ("insufficient", "Cameras that are moved, covered, dark or frozen are flagged for repair, and their sessions are never counted against the centre."),
        ("infrastructure", "Equipment seen on camera is compared with the sanctioned inventory. A shortfall triggers a photo request before any inspection is scheduled."),
        ("sync", f"The edge box sends only counts, about {sync['bytes_per_session_hour'] / 1024:.0f} kilobytes per classroom-hour, and keeps working through outages. {sync['lost_events']} records were lost in a {sync['outage_seconds']}-second outage."),
        ("results", f"Counting people in a frame takes {ms:.0f} milliseconds on a laptop CPU, so one CPU can check over a hundred cameras every ten seconds."),
    ]
