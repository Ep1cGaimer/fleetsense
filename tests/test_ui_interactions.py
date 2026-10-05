import copy
import time

import pytest
from playwright.sync_api import expect, sync_playwright

from tests.test_ui_smoke import ui_url


@pytest.fixture
def ui_page():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page(viewport={"width": 1366, "height": 1000}, reduced_motion="reduce")
        yield page
        browser.close()


@pytest.fixture
def replay_payload():
    aircraft = [
        {"aircraft": 0, "serial": "E00001", "cycle": 196, "status": "serviceable", "risk": 0.065},
        {"aircraft": 1, "serial": "E00002", "cycle": 197, "status": "serviceable", "risk": 0.96},
        {"aircraft": 2, "serial": "E00003", "cycle": 211, "status": "serviceable", "risk": 0.96},
        {"aircraft": 3, "serial": "E00004", "cycle": 123, "status": "maintenance", "risk": None},
        {"aircraft": 4, "serial": "E00005", "cycle": 160, "status": "serviceable", "risk": 0.1},
        {"aircraft": 5, "serial": "E00006", "cycle": 177, "status": "serviceable", "risk": 0.326},
    ]
    days = [{"day": day, "aircraft": copy.deepcopy(aircraft), "stock": 0, "in_shop": 3} for day in range(200)]
    days[144]["aircraft"][1]["cycle"] = 198
    for frame in days[145:]:
        frame["aircraft"][1]["serial"] = "E00007"
    return {
        "run_id": "synthetic-focused-ui-test", "data_labels": ["Synthetic UI fixture, not final evidence"],
        "days": days,
        "events": [{"day": 119, "aircraft": index, "serial": f"E{index + 1:05d}", "event": "request", "detail": {"urgency": 0.04}} for index in [0, 1, 2, 4, 5]],
        "scenario": {"aircraft": 6, "policy": "FC", "parameter": 0.02, "seed": 0, "spares": 3, "capacity": 1, "turnaround": 45},
    }


def intercept(page, name, payload):
    page.route(f"**/data/{name}.json", lambda request: request.fulfill(json=payload))


def open_page(page, ui_url, route):
    page.goto(f"{ui_url}/#/{route}")
    page.locator(f'body[data-ready="{route.split("/")[0]}"]').wait_for(timeout=15000)


@pytest.mark.ui
def test_filter_sort_nulls_and_request_scores(ui_page, ui_url, replay_payload):
    intercept(ui_page, "replay", replay_payload)
    open_page(ui_page, ui_url, "fleet")
    rows = ui_page.get_by_test_id("fleet-row")
    expect(rows).to_have_count(5)
    assert rows.evaluate_all("rows => rows.map(row => row.dataset.aircraft)") == ["1", "2", "5", "4", "0"]
    rows.first.locator("summary").click()
    expect(rows.first).to_contain_text("Request-time score: 4.0%")
    expect(rows.first).to_contain_text("96.0%")
    ui_page.get_by_test_id("fleet-filter").select_option("all")
    expect(rows).to_have_count(6)
    assert rows.last.get_attribute("data-risk") == ""
    expect(rows.last).to_contain_text("Unavailable")
    ui_page.get_by_test_id("fleet-sort").select_option("risk-asc")
    assert rows.evaluate_all("rows => rows.map(row => row.dataset.aircraft)") == ["0", "4", "5", "1", "2", "3"]
    ui_page.get_by_test_id("fleet-sort").select_option("cycles")
    assert rows.first.get_attribute("data-aircraft") == "2"
    ui_page.get_by_test_id("fleet-sort").select_option("aircraft")
    assert rows.first.get_attribute("data-aircraft") == "0"
    ui_page.get_by_test_id("fleet-search").fill("E00002")
    expect(rows).to_have_count(1)
    ui_page.get_by_test_id("fleet-filter").select_option("maintenance")
    expect(ui_page.locator("#board")).to_contain_text("No aircraft match")
    ui_page.get_by_role("button", name="Show all aircraft").click()
    expect(rows).to_have_count(6)


@pytest.mark.ui
def test_arbitrary_day_context_and_terminal_snapshot(ui_page, ui_url, replay_payload):
    intercept(ui_page, "replay", replay_payload)
    engine = {"serial": "E00002", "trajectory": "FD001-071", "cycle": 198, "sensor": "s2", "cycles": [196, 197, 198], "values": [1, 2, 3], "horizons": [10, 20], "probabilities": [0.5, 0.97], "band": {"age": [196, 197, 198], "low": [0, 1, 2], "high": [2, 3, 4]}}
    intercept(ui_page, "engine", {"engines": [engine]})
    open_page(ui_page, ui_url, "fleet")
    ui_page.get_by_test_id("fleet-search").fill("E00002")
    ui_page.get_by_test_id("fleet-sort").select_option("risk-asc")
    ui_page.get_by_test_id("aircraft-1").click()
    ui_page.locator('body[data-ready="engine"]').wait_for()
    expect(ui_page.get_by_test_id("selected-engine-context")).to_contain_text("Day 143")
    expect(ui_page.get_by_test_id("selected-engine-context")).to_contain_text("197 observed cycles")
    expect(ui_page.get_by_test_id("selected-engine-context")).to_contain_text("96.0%")
    expect(ui_page.get_by_test_id("terminal-engine-context")).to_contain_text("198 observed cycles")
    expect(ui_page.get_by_test_id("terminal-engine-context")).to_contain_text("Day 145")
    expect(ui_page.get_by_role("table", name="Terminal horizon probabilities")).to_contain_text("97.00%")
    ui_page.get_by_test_id("engine-return").click()
    ui_page.locator('body[data-ready="fleet"]').wait_for()
    ui_page.get_by_test_id("replay-day-number").fill("137")
    ui_page.get_by_test_id("replay-day-number").press("Enter")
    ui_page.get_by_test_id("aircraft-1").click()
    ui_page.locator('body[data-ready="engine"]').wait_for()
    expect(ui_page.get_by_test_id("selected-engine-context")).to_contain_text("Day 137")
    ui_page.get_by_test_id("engine-return").click()
    ui_page.locator('body[data-ready="fleet"]').wait_for()
    expect(ui_page.get_by_test_id("replay-day-number")).to_have_value("137")
    expect(ui_page.get_by_test_id("fleet-search")).to_have_value("E00002")
    expect(ui_page.get_by_test_id("fleet-sort")).to_have_value("risk-asc")
    expect(ui_page.get_by_test_id("fleet-filter")).to_have_value("pending")
    expect(ui_page.get_by_test_id("fleet-row")).to_have_count(1)


@pytest.mark.ui
def test_unknown_engine_does_not_substitute(ui_page, ui_url):
    open_page(ui_page, ui_url, "engine/NOT-AN-ENGINE")
    expect(ui_page.get_by_role("heading", name="Unknown engine ID")).to_be_visible()
    expect(ui_page.get_by_test_id("page-engine")).to_contain_text("No substitute engine is shown")
    expect(ui_page.get_by_test_id("chart-engine")).to_have_count(0)


@pytest.mark.ui
@pytest.mark.parametrize("source", ["synthetic", "exported"])
def test_real_day_fill_enter_tab_and_engine_return(ui_page, ui_url, replay_payload, source):
    if source == "synthetic":
        intercept(ui_page, "replay", replay_payload)
        intercept(ui_page, "engine", {"engines": [{"serial": "E00002", "cycle": 198, "sensor": "s2", "cycles": [198], "values": [1], "horizons": [20], "probabilities": [0.97], "band": {"age": [198], "low": [0], "high": [2]}}]})
    else:
        engines = ui_page.request.get(f"{ui_url}/data/engine.json").json()["engines"]
        if not any(engine["serial"] == "E00002" for engine in engines):
            pytest.skip("Actual E00002 replay export is not installed")
    open_page(ui_page, ui_url, "fleet")
    ui_page.get_by_test_id("fleet-filter").select_option("all")
    ui_page.get_by_test_id("fleet-search").fill("E00002")
    day_entry = ui_page.get_by_label("Go to day", exact=True)
    day_entry.fill("111")
    expect(ui_page.locator("#fleet-title")).to_contain_text("Day 111 of")
    day_entry.press("Enter")
    day_entry.press("Tab")
    expect(day_entry).to_have_value("111")
    expect(ui_page.get_by_test_id("replay-day")).to_have_value("110")
    expect(ui_page.get_by_test_id("replay-day")).to_have_attribute("aria-valuetext", "Day 111")
    expect(ui_page.locator("#history-title")).to_contain_text("Day 111")
    expect(ui_page.locator("#board thead")).to_contain_text("Model risk · Day 111")
    expect(ui_page.locator("#kpis")).to_contain_text("through Day 111")
    ui_page.get_by_test_id("aircraft-1").click()
    ui_page.locator('body[data-ready="engine"]').wait_for()
    expect(ui_page.get_by_test_id("selected-engine-context")).to_contain_text("Day 111")
    expect(ui_page.get_by_test_id("engine-return")).to_contain_text("Day 111")
    ui_page.get_by_test_id("engine-return").click()
    ui_page.locator('body[data-ready="fleet"]').wait_for()
    expect(ui_page.get_by_label("Go to day", exact=True)).to_have_value("111")
    expect(ui_page.locator("#fleet-title")).to_contain_text("Day 111 of")
    expect(ui_page.get_by_test_id("fleet-search")).to_have_value("E00002")
    expect(ui_page.get_by_test_id("fleet-filter")).to_have_value("all")


@pytest.mark.ui
def test_day_entry_explicit_enter_change_and_invalid_drafts(ui_page, ui_url, replay_payload):
    intercept(ui_page, "replay", replay_payload)
    open_page(ui_page, ui_url, "fleet")
    day_entry = ui_page.get_by_label("Go to day", exact=True)
    day_entry.focus()
    day_entry.evaluate("element => { element.value = '111'; }")
    day_entry.press("Enter")
    expect(ui_page.locator("#fleet-title")).to_contain_text("Day 111 of")
    day_entry.evaluate("element => { element.value = '112'; element.dispatchEvent(new Event('change', {bubbles: true})); }")
    expect(ui_page.get_by_test_id("replay-day")).to_have_value("111")
    day_entry.fill("")
    expect(day_entry).to_have_value("")
    expect(ui_page.locator("#fleet-title")).to_contain_text("Day 112 of")
    day_entry.press("Enter")
    expect(day_entry).to_have_value("112")
    day_entry.fill("999")
    expect(ui_page.locator("#fleet-title")).to_contain_text("Day 112 of")
    day_entry.press("Tab")
    expect(day_entry).to_have_value("112")


@pytest.mark.ui
def test_readable_lifecycle_events_preserve_raw_unknowns(ui_page, ui_url, replay_payload):
    replay_payload["events"] = [{"day": index, "serial": "E00002", "aircraft": 1, "event": name} for index, name in enumerate(["init_installed", "init_stock", "shop_return", "complete", "future_unknown_event"])]
    intercept(ui_page, "replay", replay_payload)
    intercept(ui_page, "engine", {"engines": [{"serial": "E00002", "cycle": 198, "sensor": "s2", "cycles": [198], "values": [1], "horizons": [20], "probabilities": [0.97], "band": {"age": [198], "low": [0], "high": [2]}}]})
    open_page(ui_page, ui_url, "engine/E00002")
    lifecycle = ui_page.get_by_role("table", name="Engine lifecycle events")
    for raw, label in [("init_installed", "Initially installed"), ("init_stock", "Initial shelf stock"), ("shop_return", "Overhaul return"), ("complete", "Engine-change complete"), ("future_unknown_event", "future_unknown_event")]:
        event = lifecycle.locator(f'[data-event="{raw}"]')
        expect(event).to_have_text(label)
        expect(event).to_have_attribute("title", f"Exported event: {raw}")


@pytest.mark.ui
def test_actual_export_snapshot_disclosure(ui_page, ui_url):
    replay = ui_page.request.get(f"{ui_url}/data/replay.json").json()
    engines = ui_page.request.get(f"{ui_url}/data/engine.json").json()["engines"]
    engine = next((record for record in engines if record["serial"] == "E00002"), None)
    if engine is None or len(replay["days"]) <= 142:
        pytest.skip("Actual E00002 replay export is not installed")
    observation = next(record for record in replay["days"][142]["aircraft"] if record["serial"] == "E00002")
    last_day = max(frame["day"] for frame in replay["days"] if any(record["serial"] == "E00002" for record in frame["aircraft"])) + 1
    open_page(ui_page, ui_url, "engine/E00002")
    expect(ui_page.get_by_test_id("selected-engine-context")).to_contain_text(f'{observation["cycle"]} observed cycles')
    expect(ui_page.get_by_test_id("selected-engine-context")).to_contain_text(f'{observation["risk"] * 100:.1f}%')
    expect(ui_page.get_by_test_id("terminal-engine-context")).to_contain_text(f'{engine["cycle"]} observed cycles')
    expect(ui_page.get_by_test_id("terminal-engine-context")).to_contain_text(f"Day {last_day}")
    assert observation["cycle"] == 197
    assert engine["cycle"] == 198
    assert last_day == 145


@pytest.mark.ui
def test_keyboard_replay_controls_and_play_end(ui_page, ui_url, replay_payload):
    intercept(ui_page, "replay", replay_payload)
    open_page(ui_page, ui_url, "fleet")
    slider = ui_page.get_by_test_id("replay-day")
    slider.focus()
    slider.press("ArrowRight")
    expect(ui_page.get_by_test_id("replay-day-number")).to_have_value("144")
    expect(slider).to_have_attribute("aria-valuetext", "Day 144")
    cursor = ui_page.locator(".cursor-line").get_attribute("d")
    assert cursor == f"M{48 + 143 / 199 * 940} 15V80"
    tick = ui_page.locator(".history-ticks span").filter(has_text="Day 60")
    assert tick.evaluate("element => parseFloat(element.style.left)") == pytest.approx((48 + 59 / 199 * 940) / 10, abs=0.0001)
    assert ui_page.locator(".history-ticks").evaluate("element => parseFloat(getComputedStyle(element).fontSize)") >= 13
    ui_page.get_by_role("button", name="Previous day").click()
    expect(ui_page.get_by_test_id("replay-day-number")).to_have_value("143")
    ui_page.get_by_role("button", name="Next day").click()
    expect(ui_page.get_by_test_id("replay-day-number")).to_have_value("144")
    ui_page.get_by_test_id("replay-day-number").fill("199")
    ui_page.get_by_test_id("replay-day-number").press("Enter")
    ui_page.get_by_test_id("replay-play").click()
    expect(ui_page.get_by_test_id("replay-day-number")).to_have_value("200")
    expect(ui_page.get_by_test_id("replay-play")).to_have_attribute("aria-pressed", "false")
    expect(ui_page.get_by_test_id("replay-play")).to_have_attribute("aria-label", "Play replay")
    expect(ui_page.get_by_role("button", name="Next day")).to_be_disabled()
    ui_page.get_by_test_id("replay-day-number").fill("1")
    ui_page.get_by_test_id("replay-day-number").press("Enter")
    expect(ui_page.locator("#task-summary")).to_contain_text("0 pending requests")
    expect(ui_page.locator("#board")).to_contain_text("No aircraft match")


@pytest.mark.ui
def test_horizon_numeric_tables_and_rapid_selection(ui_page, ui_url):
    payload = {"used_horizons": [10, 20, 30], "all_cycles": [], "decision_points": [], "near_threshold": [], "subgroups": []}
    for horizon in payload["used_horizons"]:
        record = {"horizon": horizon, "count": horizon * 10, "brier": horizon / 1000, "ece": 0.02, "reliability": [{"count": horizon, "prediction": horizon / 100, "observed": 0.3}]}
        payload["all_cycles"].append(record)
        payload["decision_points"].append(record)
    intercept(ui_page, "calibration", payload)
    open_page(ui_page, ui_url, "calibration")
    expect(ui_page.locator("#trust-metrics")).to_contain_text("Next 20 cycles")
    ui_page.get_by_role("button", name="10 cycles", exact=True).click()
    ui_page.get_by_role("button", name="30 cycles", exact=True).click()
    expect(ui_page.locator("#trust-metrics")).to_contain_text("Next 30 cycles")
    expect(ui_page.get_by_role("button", name="30 cycles", exact=True)).to_have_attribute("aria-pressed", "true")
    expect(ui_page.locator("#reliability-table")).to_contain_text("30.000%")
    ui_page.wait_for_function("document.querySelector('#calibration').data?.[1]?.x[0] === .3")
    expect(ui_page.locator("#trust-metrics")).to_contain_text("Unavailable")


@pytest.mark.ui
def test_unavailable_retry_and_missing_checks(ui_page, ui_url):
    failed = {"value": True}

    def replay_response(request):
        if failed["value"]:
            request.fulfill(status=503, body="Unavailable")
        else:
            request.continue_()

    ui_page.route("**/data/replay.json", replay_response)
    open_page(ui_page, ui_url, "fleet")
    expect(ui_page.get_by_role("heading", name="Evidence unavailable")).to_be_visible()
    failed["value"] = False
    ui_page.get_by_role("button", name="Retry local exports").click()
    expect(ui_page.get_by_test_id("replay-day")).to_be_visible()
    intercept(ui_page, "audits", {"scale": [], "mutations": {}, "leakage": {}, "poisoned_future": {}, "tests": {"passed": 4}})
    ui_page.get_by_role("link", name="Validation checks", exact=True).click()
    ui_page.locator('body[data-ready="audits"]').wait_for()
    check_table = ui_page.get_by_role("table", name="Recorded validation outcomes")
    assert "Recorded pass" not in check_table.inner_text()
    expect(check_table).to_contain_text("Unavailable")


@pytest.mark.ui
def test_stale_async_route_cannot_replace_current(ui_page, ui_url):
    def delayed_engine(request):
        time.sleep(0.5)
        request.continue_()

    ui_page.route("**/data/engine.json", delayed_engine)
    ui_page.goto(f"{ui_url}/#/engine", wait_until="domcontentloaded")
    ui_page.evaluate("location.hash = '#/fleet'")
    ui_page.locator('body[data-ready="fleet"]').wait_for(timeout=15000)
    expect(ui_page.get_by_test_id("page-fleet")).to_be_visible()
    expect(ui_page.get_by_test_id("page-engine")).to_have_count(0)


@pytest.mark.ui
@pytest.mark.parametrize("width", [390, 768, 1366, 1920])
@pytest.mark.parametrize("route", ["fleet", "engine", "policies", "calibration", "audits"])
def test_responsive_layout_and_desktop_table(ui_page, ui_url, width, route):
    ui_page.set_viewport_size({"width": width, "height": 1000})
    open_page(ui_page, ui_url, route)
    ui_page.evaluate("document.fonts.ready")
    assert ui_page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    if route == "fleet" and width >= 1366:
        assert ui_page.locator("#board .table-wrap").evaluate("element => element.scrollWidth <= element.clientWidth")
        bounds = ui_page.locator(".fleet-grid").evaluate("element => ({bottom: element.getBoundingClientRect().bottom, top: element.getBoundingClientRect().top, children: Array.from(element.children).map(child => child.getBoundingClientRect().height)})")
        assert bounds["bottom"] <= 1300, str(bounds)


@pytest.mark.ui
def test_policy_registered_verdict_and_numeric_evidence(ui_page, ui_url):
    open_page(ui_page, ui_url, "policies")
    expect(ui_page.get_by_role("table", name="Frozen policy outcomes")).to_be_visible()
    expect(ui_page.get_by_role("table", name="Scenario matrix")).to_be_visible()
    expect(ui_page.get_by_test_id("page-policies")).to_contain_text("percentage points above")
    text = ui_page.get_by_test_id("page-policies").inner_text()
    for prohibited in ["Highest availability", "Predictive removal leads", "Run maintenance strategies", "Remove now"]:
        assert prohibited not in text


@pytest.fixture
def finder_engines():
    return {"engines": [{"serial": serial, "trajectory": source, "cycle": cycle, "sensor": "s2", "cycles": [cycle], "values": [1.25], "horizons": [20], "probabilities": [risk], "band": {"age": [cycle], "low": [0.5], "high": [2.5]}} for serial, source, cycle, risk in [("E00002", "FD001-071", 198, 0.97), ("E00003", "FD003-084", 211, 0.96), ("E90000", "FD001-099", 80, None)]]}


@pytest.mark.ui
def test_stores_initial_state_replacement_and_singular_copy(ui_page, ui_url, replay_payload, finder_engines):
    replay_payload["events"] = [
        {"day": -1, "aircraft": 1, "serial": "E00002", "event": "init_installed", "detail": {"cycle": 55}},
        {"day": -1, "aircraft": -1, "serial": "E00003", "event": "init_stock", "detail": {"cycle": 0}},
        {"day": 100, "aircraft": -1, "serial": "E00002", "event": "shop_return", "detail": {"new_serial": "E00003"}},
        {"day": 101, "aircraft": None, "serial": "E90000", "event": "failure", "detail": {}},
        {"day": 109, "aircraft": 1, "serial": "E00002", "event": "request", "detail": {"urgency": 0.04}},
    ]
    replay_payload["days"][110]["stock"] = 1
    intercept(ui_page, "replay", replay_payload)
    intercept(ui_page, "engine", finder_engines)
    open_page(ui_page, ui_url, "fleet")
    ui_page.get_by_label("Go to day", exact=True).fill("111")
    expect(ui_page.locator("#task-summary")).to_have_text("1 pending request. 1 shelf spare available.")
    expect(ui_page.locator("#board")).to_contain_text("pending 1 day")
    events = ui_page.get_by_test_id("replay-events")
    expect(events).to_contain_text("Stores / spare pool")
    expect(events).to_contain_text("Replacement lifecycle ID: E00003")
    assert "AF-00" not in events.inner_text()
    ui_page.get_by_test_id("aircraft-1").click()
    ui_page.locator('body[data-ready="engine"]').wait_for()
    lifecycle = ui_page.get_by_role("table", name="Engine lifecycle events")
    expect(lifecycle).to_contain_text("Initial state — before Day 1")
    expect(lifecycle).to_contain_text("Stores / spare pool")
    expect(lifecycle).to_contain_text("Replacement lifecycle ID: E00003")
    assert "AF-00" not in lifecycle.inner_text()
    assert "Day 0" not in lifecycle.inner_text()
    ui_page.get_by_label("Exported engines", exact=True).get_by_role("link").filter(has_text="E00003").click()
    ui_page.locator('body[data-ready="engine"]').wait_for()
    expect(ui_page.get_by_role("table", name="Engine lifecycle events")).to_contain_text("lifecycle E00002")
    expect(ui_page.get_by_test_id("engine-return")).to_contain_text("Day 111")


@pytest.mark.ui
def test_local_engine_finder_serial_source_empty_clear_and_context(ui_page, ui_url, replay_payload, finder_engines):
    intercept(ui_page, "replay", replay_payload)
    intercept(ui_page, "engine", finder_engines)
    open_page(ui_page, ui_url, "fleet")
    ui_page.get_by_test_id("fleet-filter").select_option("all")
    ui_page.get_by_test_id("fleet-search").fill("E00002")
    ui_page.get_by_label("Go to day", exact=True).fill("111")
    ui_page.get_by_test_id("aircraft-1").click()
    ui_page.locator('body[data-ready="engine"]').wait_for()
    finder = ui_page.get_by_label("Find engine by serial or source", exact=True)
    rail = ui_page.get_by_role("navigation", name="Exported engines", exact=True)
    expect(rail.get_by_role("link")).to_have_count(3)
    assert "terminal export" not in rail.inner_text().lower()
    finder.fill("fd003-084")
    expect(rail.get_by_role("link")).to_have_count(1)
    rail.get_by_role("link").click()
    ui_page.locator('body[data-ready="engine"]').wait_for()
    expect(ui_page.get_by_label("Find engine by serial or source", exact=True)).to_have_value("fd003-084")
    expect(rail.locator('[aria-current="page"]')).to_contain_text("E00003")
    finder.fill("E90000")
    expect(rail.get_by_role("link")).to_have_count(1)
    expect(rail).to_contain_text("FD001-099")
    finder.fill("not-exported")
    expect(rail.get_by_role("link")).to_have_count(0)
    expect(rail).to_contain_text("No exported engines match")
    ui_page.get_by_role("button", name="Clear engine search", exact=True).click()
    expect(finder).to_have_value("")
    expect(finder).to_be_focused()
    expect(rail.get_by_role("link")).to_have_count(3)
    ui_page.get_by_test_id("engine-return").click()
    ui_page.locator('body[data-ready="fleet"]').wait_for()
    expect(ui_page.get_by_label("Go to day", exact=True)).to_have_value("111")
    expect(ui_page.get_by_test_id("fleet-search")).to_have_value("E00002")
    expect(ui_page.get_by_test_id("fleet-filter")).to_have_value("all")


@pytest.mark.ui
def test_engine_section_jumps_numeric_disclosures_and_sticky_return(ui_page, ui_url, replay_payload, finder_engines):
    intercept(ui_page, "replay", replay_payload)
    intercept(ui_page, "engine", finder_engines)
    open_page(ui_page, ui_url, "engine/E00002")
    ui_page.get_by_role("link", name="Sensor history", exact=True).click()
    assert ui_page.evaluate("location.hash") == "#/engine/E00002"
    expect(ui_page.locator("#engine-history")).to_be_focused()
    ui_page.get_by_role("link", name="View sensor values", exact=True).click()
    expect(ui_page.locator("#engine-sensor-values")).to_have_attribute("open", "")
    expect(ui_page.get_by_role("table", name="Engine sensor readings")).to_contain_text("1.2500")
    expect(ui_page.get_by_role("table", name="Training-engine reference quantiles")).to_contain_text("2.5000")
    ui_page.get_by_role("link", name="Horizon probabilities", exact=True).click()
    ui_page.get_by_role("link", name="View horizon values", exact=True).click()
    expect(ui_page.locator("#engine-horizon-values")).to_be_focused()
    expect(ui_page.get_by_role("table", name="Terminal horizon probabilities")).to_contain_text("97.00%")
    ui_page.get_by_role("link", name="Lifecycle evidence", exact=True).click()
    expect(ui_page.locator("#engine-lifecycle")).to_be_focused()
    assert ui_page.locator(".workspace-context").evaluate("element => getComputedStyle(element).position") == "sticky"
    assert ui_page.locator(".workspace-context").evaluate("element => element.getBoundingClientRect().top >= -1")
    expect(ui_page.get_by_test_id("engine-return")).to_be_in_viewport()
    expect(ui_page.locator("#workspace-scope")).to_contain_text("terminal export: cycle 198")


@pytest.mark.ui
def test_policy_dimensions_parameters_and_numeric_jumps(ui_page, ui_url):
    summary = {"verdict": "REFUTED", "primary": {"ci95_pp": [-0.07, 0.32]}, "study_design": {"policies": {code: {"recorded_parameter": value, "selection_mode": "fewest_failures_fallback"} for code, value in [("HT", 100), ("CT", 0.4), ("FC", 0.02), ("unknown", None)]}}}
    summary["study_design"]["policies"]["unknown"]["selection_mode"] = "future_selection_rule"
    cells = [{"rate": 1.0, "downtime_ratio": 8, "turnaround": 45, "delta_availability_pp": -0.125, "ci95_pp": [-0.5, 0.25]}]
    intercept(ui_page, "summary", summary)
    intercept(ui_page, "policies", {"cells": cells, "frontier": [{"policy": "HT", "parameter": 100, "availability": 0.9}], "metrics": {}})
    open_page(ui_page, ui_url, "policies")
    ui_page.get_by_role("link", name="Trade-off and scenarios", exact=True).click()
    expect(ui_page.locator("#policy-charts")).to_be_focused()
    expect(ui_page.locator(".dimension-key")).to_contain_text("unplanned / planned downtime")
    dimension = ui_page.get_by_role("button", name="8× / 45d: unplanned / planned downtime ratio 8 times; overhaul turnaround 45 days. Open scenario table.", exact=True)
    dimension.focus()
    expect(ui_page.locator("#scenario-dimension-detail")).to_contain_text("overhaul turnaround: 45 days")
    dimension.hover()
    expect(ui_page.locator("#scenario-dimension-detail")).to_contain_text("ratio: 8 times")
    assert ui_page.locator("#policies").evaluate("element => element.data[0].z[0][0]") == -0.125
    assert "95% CI: -0.500 to 0.250 pp" in ui_page.locator("#policies").evaluate("element => element.data[0].customdata[0][0]")
    ui_page.get_by_role("link", name="View frontier numeric values", exact=True).click()
    expect(ui_page.locator("#frontier-values")).to_have_attribute("open", "")
    expect(ui_page.get_by_role("table", name="Frontier alternatives")).to_contain_text("100 cycles")
    assert ui_page.evaluate("location.hash") == "#/policies"
    ui_page.get_by_role("link", name="View scenario numeric values", exact=True).click()
    expect(ui_page.locator("#scenario-table")).to_be_focused()
    expect(ui_page.get_by_role("table", name="Scenario matrix")).to_contain_text("-0.500 to 0.250")
    expect(ui_page.locator(".workspace-context")).to_contain_text("simulated squadron-years per strategy")


@pytest.mark.ui
@pytest.mark.parametrize("route, control, target", [("calibration", "View reliability numeric values", "calibration-values")])
def test_secondary_workspace_scope_and_disclosure_jumps(ui_page, ui_url, route, control, target):
    open_page(ui_page, ui_url, route)
    ui_page.get_by_role("link", name=control, exact=True).click()
    expect(ui_page.locator(f"#{target}")).to_have_attribute("open", "")
    expect(ui_page.locator(f"#{target}")).to_be_focused()
    assert ui_page.evaluate("location.hash") == f"#/{route}"
    expect(ui_page.get_by_role("link", name="Return to Fleet replay", exact=True)).to_be_in_viewport()
    if route == "calibration":
        ui_page.get_by_role("link", name="Horizon scores", exact=True).click()
        ui_page.get_by_role("button", name="10 cycles", exact=True).click()
        expect(ui_page.locator("#workspace-scope")).to_contain_text("Next 10 cycles")
