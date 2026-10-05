import hashlib
import sys
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fleetsense.common import ROOT

URL = "https://phm-datasets.s3.amazonaws.com/NASA/6.+Turbofan+Engine+Degradation+Simulation+Data+Set.zip"


def extract_safe(archive, destination):
    destination = destination.resolve()
    with zipfile.ZipFile(archive) as source:
        for item in source.infolist():
            target = (destination / item.filename).resolve()
            if not target.is_relative_to(destination):
                raise ValueError("Unsafe archive path")
        source.extractall(destination)


def main():
    raw = ROOT / "data/raw"
    raw.mkdir(parents=True, exist_ok=True)
    archive = raw / "cmapps.zip"
    if not archive.exists():
        print("Downloading public simulated engine benchmark", flush=True)
        urllib.request.urlretrieve(URL, archive)
    if not all(list(raw.rglob(f"train_{subset}.txt")) for subset in ("FD001", "FD003")):
        extract_safe(archive, raw / "extracted")
        for nested in (raw / "extracted").rglob("*.zip"):
            extract_safe(nested, nested.with_suffix(""))
    lines = []
    for subset in ("FD001", "FD003"):
        path = next(raw.rglob(f"train_{subset}.txt"))
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.relative_to(raw).as_posix()}")
    (raw / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Dataset downloaded and train-file hashes written", flush=True)


if __name__ == "__main__":
    main()
