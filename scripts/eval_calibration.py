import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fleetsense.calibration import evaluate_calibration
from fleetsense.common import ROOT, assert_lock, read_config, write_json


def main():
    assert_lock()
    tables = pd.read_parquet(ROOT / "artifacts/test_tables.parquet")
    decisions = pd.read_parquet(ROOT / "artifacts/decision_points.parquet").to_records(index=False).tolist()
    result = evaluate_calibration(tables, decisions, read_config()["tuning"]["selected"]["FC"])
    write_json(ROOT / "results/calibration.json", result)


if __name__ == "__main__":
    main()
