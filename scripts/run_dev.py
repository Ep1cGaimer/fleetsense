import argparse
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fleetsense.common import ROOT, read_config, read_json, write_json
from fleetsense.data import create_splits, load_split
from fleetsense.experiments import execute, scenarios, time_bootstrap
from fleetsense.statistics import aggregate, select_parameter
from fleetsense.training import build_oof


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reuse-oof", action="store_true")
    args = parser.parse_args()
    if (ROOT / "results/prereg.lock").exists():
        raise RuntimeError("Dev tuning is forbidden after the preregistration lock")
    config = read_config()
    if not (ROOT / "data/splits.json").exists():
        create_splits()
    split = read_json(ROOT / "data/splits.json")
    if not args.reuse_oof:
        build_oof()
    raw = load_split("dev")
    failures = raw.groupby("engine").cycle.max().to_dict()
    tasks = []
    for policy in ("HT", "CT", "FC"):
        for parameter in config["tuning"][policy.lower()]:
            tasks.append((f"tune_{policy}_{parameter}", split["dev"], scenarios(config["tuning"]["seeds"]),
                          [(policy, parameter)], str(ROOT / "results/dev/tuning"), False))
    rows, _ = execute(tasks, ROOT / "artifacts/oof_tables.parquet", failures)
    tuning_rows = []
    selected = {}
    for policy in ("HT", "CT", "FC"):
        for parameter in config["tuning"][policy.lower()]:
            metrics = aggregate([row for row in rows if row["policy"] == policy and row["parameter"] == parameter])
            tuning_rows.append({"policy": policy, "parameter": parameter, **metrics})
        chosen = select_parameter([row for row in tuning_rows if row["policy"] == policy], config["tuning"]["failure_budget"])
        selected[policy] = chosen["parameter"]
    simple = select_parameter([row for row in tuning_rows if row["policy"] in {"HT", "CT"}
                               and row["parameter"] == selected[row["policy"]]], config["tuning"]["failure_budget"])
    selected["best_simple"] = simple["policy"]
    dry = time_bootstrap(ROOT / "artifacts/oof_tables.parquet", failures, split["dev"],
                         [("FC", selected["FC"]), (simple["policy"], selected[simple["policy"]])])
    replicates = config["evaluation"]["bootstrap_upgrade_replicates"] if dry["estimated_500_seconds"] < config["evaluation"]["bootstrap_upgrade_if_dry_seconds_below"] else 200
    config["evaluation"]["bootstrap_replicates"] = replicates
    config["tuning"]["selected"] = selected
    config["data"]["splits_sha256"] = __import__("hashlib").sha256((ROOT / "data/splits.json").read_bytes()).hexdigest()
    (ROOT / "config/prereg.yaml").write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    write_json(ROOT / "results/tuning.json", {"evaluation_kind": "dev_only", "rows": tuning_rows, "selected": selected, "runs": len(rows), "dry_run": dry})
    with (ROOT / "DECISIONS.md").open("a", encoding="utf-8") as output:
        output.write(f"\n## Dev-only runtime decision\n\nMeasured {dry['replicates_timed']} hierarchical replicates in {dry['wall_seconds']:.3f} seconds; "
                     f"estimated 500-replicate workload {dry['estimated_500_seconds']:.3f} seconds. Locked bootstrap count: {replicates}. "
                     "The timing benchmark includes simulator, independent checker and event serialization. No test engines were accessed.\n")
    print(f"Tuning complete: {selected}; bootstrap={replicates}", flush=True)


if __name__ == "__main__":
    main()
