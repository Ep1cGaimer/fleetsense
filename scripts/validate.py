import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fleetsense.common import ROOT, write_json


def main():
    process = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT, text=True, capture_output=True)
    print(process.stdout)
    print(process.stderr)
    if process.returncode:
        raise SystemExit(process.returncode)
    passed = re.search(r"(\d+) passed", process.stdout)
    write_json(ROOT / "results/prelock_tests.json", {"passed": int(passed.group(1)), "failed": 0,
                                                    "output": process.stdout.strip(),
                                                    "ui_kind": "Synthetic functional fixture before final export; not final measurement"})


if __name__ == "__main__":
    main()
