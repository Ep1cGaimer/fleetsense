import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fleetsense.common import ROOT, assert_lock, read_json, write_json
from fleetsense.reporting import allowed_numbers, claims, presentation
from scripts.export_ui_data import export
from scripts.make_claims import generate
from scripts.exploratory_tradeoffs import main as exploratory_tradeoffs


def refresh(summary):
    summary["claims"] = claims(summary)
    deviations = [row for row in summary.get("deviations", [])
                  if row.get("kind") not in {"reporting_scope", "tuning_feasibility"}]
    deviations.extend([
        {"kind": "reporting_scope", "status": "Deviation", "source": "DEVIATIONS.md",
         "reason": "Lifecycle-instance serials are demonstrated; physical-component serial continuity is not established."},
        {"kind": "tuning_feasibility", "status": "Deviation", "source": "docs/STUDY_DESIGN_REVIEW.md",
         "reason": "No HT, CT or FC development candidate met the failure budget; all thresholds used the registered fewest-failures fallback. No final policy or verdict is changed."}])
    summary["deviations"] = deviations
    summary["presentation"] = presentation(summary)
    summary["study_design"] = {
        **summary["presentation"]["tuning_feasibility"],
        "status": "Deviation",
        "scope_warning": "No development policy met the failure budget, so all used fewest-failures fallbacks; REFUTED concerns these frozen policies in tested scenarios, not forecasting in general.",
        "scope_caveat": "REFUTED concerns the frozen fallback policies in the tested range, not forecasting generally or availability-optimal policies under a feasible failure budget.",
        "test_frontier_scope": "Registered reporting-only test frontier; no retuning or replacement final policy.",
        "review": "docs/STUDY_DESIGN_REVIEW.md",
        "exploratory_report": "results/exploratory_tradeoffs.json"}
    summary["presentation"]["allowed_numbers"] = allowed_numbers(summary)
    return summary


def main():
    assert_lock()
    summary = read_json(ROOT / "results/summary.json")
    refresh(summary)
    exploratory_tradeoffs()
    write_json(ROOT / "results/summary.json", summary)
    export(summary)
    generate(summary)
    print("Report scope clarified without changing any measured statistic")


if __name__ == "__main__":
    main()
