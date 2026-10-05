import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fleetsense.common import ROOT, git, read_config, sha256


def main():
    config = read_config()
    if not config["tuning"]["selected"]:
        raise RuntimeError("Complete dev tuning before locking")
    if config["data"]["splits_sha256"] != sha256(ROOT / "data/splits.json"):
        raise RuntimeError("Split hash mismatch")
    lock_path = ROOT / "results/prereg.lock"
    if lock_path.exists():
        raise RuntimeError("Preregistration is already locked")
    lock_path.parent.mkdir(exist_ok=True)
    lock_path.write_text(sha256(ROOT / "config/prereg.yaml") + "\n", encoding="utf-8")
    git("add", "config/prereg.yaml", "results/prereg.lock", "data/splits.json", "results/tuning.json", "results/sensor_list.json", "DECISIONS.md", "DEVIATIONS.md")
    git("commit", "-m", "prereg: lock before test evaluation")
    print(f"Locked at {git('rev-parse', 'HEAD')}", flush=True)


if __name__ == "__main__":
    main()
