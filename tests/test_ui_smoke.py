import socket
import os
import subprocess
import sys
import time
from urllib.parse import urlparse

import pytest
from playwright.sync_api import sync_playwright

from fleetsense.common import ROOT


@pytest.fixture(scope="module")
def ui_url(tmp_path_factory):
    environment = os.environ.copy()
    if not (ROOT / "results/ui/summary.json").exists():
        from tests.ui_fixture import synthetic_ui_fixture
        directory = tmp_path_factory.mktemp("synthetic-ui-not-final")
        synthetic_ui_fixture(directory)
        environment["FLEETSENSE_UI_DATA"] = str(directory)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    process = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.server:app", "--host", "127.0.0.1", "--port", str(port)],
                               cwd=ROOT, env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            with socket.socket() as connection:
                if connection.connect_ex(("127.0.0.1", port)) == 0:
                    break
            if process.poll() is not None:
                raise RuntimeError("UI server failed to start")
            time.sleep(0.1)
        else:
            raise RuntimeError("UI server did not start")
        yield f"http://127.0.0.1:{port}"
    finally:
        process.terminate()
        process.wait(timeout=10)


@pytest.mark.ui
@pytest.mark.parametrize("route", ["fleet", "engine", "policies", "calibration", "audits"])
def test_ui_routes(ui_url, route):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page(viewport={"width": 1366, "height": 768})
        errors, external = [], []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
        page.on("request", lambda request: external.append(request.url) if urlparse(request.url).hostname not in {None, "127.0.0.1"} else None)
        page.goto(f"{ui_url}/#/{route}")
        page.locator(f'body[data-ready="{route}"]').wait_for(timeout=10000)
        assert page.get_by_test_id(f"page-{route}").count() == 1
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        assert not errors
        assert not external
        browser.close()
