import hashlib
import json
import subprocess
from functools import lru_cache
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@lru_cache(maxsize=1)
def read_config():
    return yaml.safe_load((ROOT / "config/prereg.yaml").read_text(encoding="utf-8"))


def json_default(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(type(value).__name__)


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, default=json_default, allow_nan=False) + "\n", encoding="utf-8")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def assert_lock(clean=False):
    lock = (ROOT / "results/prereg.lock").read_text().strip()
    if sha256(ROOT / "config/prereg.yaml") != lock:
        raise RuntimeError("Preregistration hash mismatch; evaluation refused")
    if clean and git("status", "--porcelain"):
        raise RuntimeError("Git tree must be clean before final evaluation, including untracked files")
    return lock
