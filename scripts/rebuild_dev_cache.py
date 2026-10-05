import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fleetsense.common import ROOT, assert_lock, read_config, read_json
from fleetsense.training import build_table


def main():
    assert_lock()
    from fleetsense.data import load_split
    import pandas as pd
    raw = load_split("dev")
    split = read_json(ROOT / "data/splits.json")
    tables, metadata = [], []
    for fold in range(read_config()["data"]["folds"]):
        train_ids = sorted(split["folds"][(fold + 2) % 4] + split["folds"][(fold + 3) % 4])
        table, item = build_table(raw, train_ids, split["folds"][(fold + 1) % 4], split["folds"][fold], f"fold{fold}")
        tables.append(table)
        metadata.append(item)
    pd.concat(tables, ignore_index=True).to_parquet(ROOT / "artifacts/oof_tables.parquet", index=False)
    from fleetsense.common import write_json
    write_json(ROOT / "artifacts/oof_metadata.json", metadata)


if __name__ == "__main__":
    main()
