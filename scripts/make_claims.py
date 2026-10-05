import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fleetsense.common import ROOT, assert_lock, read_json, write_json
from fleetsense.reporting import claims


def generate(summary):
    assert_lock()
    rows = claims(summary)
    lines = ["# FleetSense claim ledger", "", f"Generated from locked final run `{summary['run_id']}`.", "",
             "| Claim | Status | Evidence |", "|---|---|---|"]
    lines.extend(f"| {row['claim']} | {row['status']} | {row['evidence']} |" for row in rows)
    (ROOT / "CLAIMS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    write_json(ROOT / "results/claim_table.json", rows)
    write_json(ROOT / "results/ui/claims.json", {"schema_version": 1, "run_id": summary["run_id"],
                                               "data_labels": summary["data_labels"], "claims": rows})
    lines = ["# FleetSense", "", "Readiness evidence before adopting predictive maintenance.", "",
             "; ".join(summary["data_labels"]), "", "## Registered result", "", summary["verdict_text"], "",
             "Every outcome is first-class: SUPPORTED requires the meaningful gain and every guardrail; REFUTED rules out the meaningful gain; INCONCLUSIVE is the remainder.", "",
             "## Evidence", ""]
    lines.extend(f"- {item}" for item in summary["presentation"]["facts"])
    lines.extend([f"- {summary['tests_passed']} tests passed; {summary['checker_violations']} independent-checker violations.",
                  f"- {summary['primary']['bootstrap_replicates']} hierarchical engine-and-scenario resamples.", "", "## Limitations", ""])
    lines.extend(f"- {item}" for item in summary["presentation"]["limitations"])
    lines.extend(["", "## Reproduce", "", "Run `scripts/reproduce.ps1` from a clean checkout. Raw data and model caches are ignored; locked configuration, split hashes and result manifests are committed.",
                  "", "## Local UI", "", "Run `.venv/Scripts/python.exe -m app.server`, then open the loopback address printed by the server. No model computation happens in the server. Every chart reads exported evidence only.",
                  "", "See `PREREGISTRATION.md`, `DECISIONS.md`, `DEVIATIONS.md`, `CLAIMS.md`, `app/ui/DATA.md`, and `results/manifest.json`.",
                  "", "Submission links remain `{REPO_URL}` and `{VIDEO_URL}` until the user supplies them. No remote is configured and nothing is pushed."])
    lines.extend(["", "## Outcome templates", "", "These are templates, not additional findings:", ""])
    for outcome, template in summary["presentation"]["verdict_templates"].items():
        lines.append(f"- {outcome}: {template}")
    (ROOT / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    generate(read_json(ROOT / "results/summary.json"))
