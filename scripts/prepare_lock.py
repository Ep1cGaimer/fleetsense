import platform
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fleetsense.common import ROOT, read_config, read_json, sha256, write_json
from fleetsense.data import load_split, raw_paths
from fleetsense.features import sensor_list


def main():
    if (ROOT / "results/prereg.lock").exists():
        raise RuntimeError("Pre-lock preparation cannot run after locking")
    config = read_config()
    config["data"]["raw_sha256"] = {subset: sha256(path) for subset, path in raw_paths().items()}
    config["presentation"]["ui_port"] = 8601
    config["presentation"]["python_version"] = platform.python_version()
    config["presentation"]["slide_ordinals"] = [1, 2, 3, 4, 5, 6]
    split = read_json(ROOT / "data/splits.json")
    training_ids = [engine for fold in split["folds"][:3] for engine in fold]
    raw = load_split("dev")
    sensors = sensor_list(raw.loc[raw.engine.isin(training_ids)])
    lists = read_json(ROOT / "results/sensor_list.json")
    lists["final_training_only"] = sensors
    write_json(ROOT / "results/sensor_list.json", lists)
    config["data"]["final_training_sensors"] = sensors
    (ROOT / "config/prereg.yaml").write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    with (ROOT / "DECISIONS.md").open("a", encoding="utf-8") as output:
        output.write("\n## Final training sensor list before lock\n\n" + ", ".join(sensors) + ". Selected on final training dev folds only, without test access.\n")
    import plotly
    vendor = ROOT / "app/ui/vendor"
    lines = ["# Vendored offline assets", "", f"Plotly Python package version: {plotly.__version__}.", "",
             "Plotly.js: MIT licence, https://github.com/plotly/plotly.js/blob/master/LICENSE.",
             "Inter and JetBrains Mono: accompanying copied font licence in LICENSE.txt.", "", "| File | SHA-256 |", "|---|---|"]
    for path in sorted(vendor.iterdir()):
        if path.is_file() and path.name != "VENDOR.md":
            lines.append(f"| {path.name} | {sha256(path)} |")
    (vendor / "VENDOR.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
