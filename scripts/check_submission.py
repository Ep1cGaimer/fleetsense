from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

import fitz

from media_common import IS_FLEET, PS, ROOT, summary

NUMBER = re.compile(r"(?<![\w.])[-+]?\d+(?:\.\d+)?(?![\w.])")
BANNED = re.compile(r"\b(?:proves|guarantees|compliant|fraud|ghost)\b|novel architecture", re.IGNORECASE)


def number_set(value):
    allowed = set()
    if isinstance(value, dict):
        for item in value.values():
            allowed.update(number_set(item))
    elif isinstance(value, list):
        for item in value:
            allowed.update(number_set(item))
    elif isinstance(value, str):
        allowed.update(float(match) for match in NUMBER.findall(value))
    elif isinstance(value, (float, int)) and not isinstance(value, bool):
        for scale in (1, 100):
            for places in range(7):
                allowed.add(round(value * scale, places))
    return allowed


def lock_digest():
    text = (ROOT / "results/prereg.lock").read_text(encoding="utf-8-sig").strip()
    try:
        data = json.loads(text)
        return data.get("sha256", data.get("prereg_sha256")) if isinstance(data, dict) else data
    except json.JSONDecodeError:
        return text.split()[0]


def main(args):
    checks = []
    blockers = []

    def check(label, passed, detail=""):
        checks.append({"check": label, "passed": bool(passed), "detail": str(detail)})

    result = summary()
    toolkit = json.loads((ROOT / "submission/toolkit_manifest.json").read_text(encoding="utf-8"))
    drift = [relative for relative, expected in toolkit["sha256"].items()
             if not (ROOT / relative).exists() or hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != expected]
    check("Canonical toolkit snapshot", not drift, drift)
    pdf_path = ROOT / "submission" / (PS + "_Idea.pdf")
    video_path = ROOT / "submission" / (PS + "_demo.mp4")
    if pdf_path.exists():
        document = fitz.open(pdf_path)
        text = "\n".join(page.get_text() for page in document)
        check("PDF page count", len(document) == 6, len(document))
        check("Text-extractable PDF", all(len(page.get_text().strip()) > 60 for page in document))
        check("PDF below portal size limit", pdf_path.stat().st_size < 10_000_000, pdf_path.stat().st_size)
        placeholders = sorted(set(re.findall(r"\[TEAM ID\]|\{REPO_URL\}|\{VIDEO_URL\}|\{[^}]*\}", text)))
        if placeholders:
            blockers.extend(placeholders)
        check("No submission placeholders", not placeholders, placeholders)
        numeric = number_set(result)
        build_path = ROOT / "submission/build_manifest.json"
        build_inputs = json.loads(build_path.read_text(encoding="utf-8"))
        numeric.update(number_set(build_inputs["team_id"]))
        facts = ROOT / "submission/deck" / ("cited_facts_fleetsense.json" if IS_FLEET else "cited_facts_centresight.json")
        if facts.exists():
            numeric.update(float(row["value"]) for row in json.loads(facts.read_text(encoding="utf-8")))
        numeric_text = re.sub(r"https?://\S+", "", text)
        numbers = set(float(value) for value in NUMBER.findall(numeric_text))
        unknown = sorted(numbers - numeric)
        check("PDF number provenance", not unknown, unknown)
        check("Deck uses current measured summary", build_inputs["summary_sha256"] == hashlib.sha256((ROOT / "results/summary.json").read_bytes()).hexdigest())
        check("PDF banned-word scan", not BANNED.search(text))
        if IS_FLEET:
            check("Simulated benchmark labelled honestly", "real data" not in text.lower())
        document.close()
    else:
        check("PDF exists", False, pdf_path)
    digest = hashlib.sha256((ROOT / "config/prereg.yaml").read_bytes()).hexdigest()
    check("Preregistration hash", digest == lock_digest() == result.get("prereg_sha256"))
    check("Completed measured verdict", result.get("verdict") in {"SUPPORTED", "INCONCLUSIVE", "REFUTED"})
    sys.path.insert(0, str(ROOT))
    if IS_FLEET:
        from fleetsense.statistics import verdict, verdict_text
        computed = verdict(result["primary"], result["guardrails"])
        regenerated = verdict_text(computed, result["primary"], result["guardrails"]["failures"])
    else:
        from centresight.evaluation import verdict, verdict_text
        computed = verdict(result["primary"]["delta_pp"], result["primary"]["ci_pp"], result["primary"]["mwi_pp"])
        regenerated = verdict_text({**result, "verdict": computed})
    check("Verdict recomputed from measured inputs", computed == result["verdict"])
    check("Verdict wording recomputed from measured inputs", regenerated == result["verdict_text"])
    if IS_FLEET:
        violations = result.get("checker_violations", result.get("audits", {}).get("checker_violations"))
        check("Independent checker", violations == 0, violations)
    else:
        sync = result.get("sync", result.get("audits", {}).get("sync", {}))
        privacy = result.get("privacy", result.get("audits", {}).get("privacy", {}))
        sync_pass = sync.get("passed", sync.get("no_loss", False) and sync.get("no_duplicates", False))
        privacy_pass = privacy.get("passed", privacy.get("unauthorised_images", -1) == 0)
        check("Measured sync test", sync_pass, sync)
        check("Measured privacy test", privacy_pass, privacy)
    manifest_path = ROOT / "results/manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        tests = manifest.get("tests", {})
        count = result.get("tests_passed", tests.get("passed", manifest.get("tests_passed", 0)))
        failed = tests.get("failed", manifest.get("tests_failed", 0))
        check("Executed pytest evidence", count > 0 and failed == 0, {"passed": count, "failed": failed})
    else:
        check("Run manifest exists", False)
    scan_paths = [ROOT / "README.md", ROOT / "docs/narration.yaml", ROOT / "submission/IDEA_DESCRIPTION.md"]
    for directory in (ROOT / "app/ui", ROOT / "server/ui"):
        if directory.exists():
            scan_paths.extend(item for item in directory.rglob("*") if item.suffix in {".html", ".js", ".css"} and "vendor" not in item.parts)
    offending = []
    for path in scan_paths:
        if path.exists():
            match = BANNED.search(path.read_text(encoding="utf-8-sig"))
            if match:
                offending.append(str(path.relative_to(ROOT)) + ": " + match.group())
    check("User-facing copy scan", not offending, offending)
    if video_path.exists():
        probe = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(video_path)], capture_output=True, text=True, check=True)
        data = json.loads(probe.stdout)
        videos = [stream for stream in data["streams"] if stream["codec_type"] == "video"]
        audio = [stream for stream in data["streams"] if stream["codec_type"] == "audio"]
        check("Video duration", float(data["format"]["duration"]) <= 195, data["format"]["duration"])
        check("Video resolution", bool(videos) and videos[0]["width"] == 1920 and videos[0]["height"] == 1080)
        video_manifest = json.loads((ROOT / "results/video_manifest.json").read_text(encoding="utf-8"))
        check("Audio or documented captions-only mode", bool(audio) or video_manifest.get("captions_only", False))
    else:
        check("Video exists", False, video_path)
    link_pattern = re.compile(r"https://(?:github\.com|youtu\.be|www\.youtube\.com)/[^\s)]+")
    portal_path = ROOT / "submission/IDEA_DESCRIPTION.md"
    if not blockers and portal_path.exists():
        links = set(link_pattern.findall(portal_path.read_text(encoding="utf-8")))
        check("Repository and video links present", len(links) >= 2)
        for link in sorted(links):
            try:
                with urllib.request.urlopen(link, timeout=20) as response:
                    check("Published link: " + link, response.status == 200)
            except OSError as error:
                check("Published link: " + link, False, error)
    report = {"passed": all(item["passed"] for item in checks), "handoff_placeholders": blockers, "checks": checks}
    target = ROOT / "results/submission_check.json"
    target.write_text(json.dumps(report, indent=2), encoding="utf-8")
    for item in checks:
        print(("PASS " if item["passed"] else "FAIL ") + item["check"] + (": " + item["detail"] if item["detail"] else ""))
    only_placeholders = all(item["passed"] or item["check"] == "No submission placeholders" for item in checks)
    if not report["passed"] and not (args.allow_handoff_placeholders and only_placeholders):
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-handoff-placeholders", action="store_true")
    main(parser.parse_args())
