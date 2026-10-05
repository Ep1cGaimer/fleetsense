param([switch]$SkipArtifacts, [switch]$VerifyExisting)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root
if ($VerifyExisting) {
    $started = Get-Date
    $python = if ($env:FLEETSENSE_VERIFY_PYTHON) { $env:FLEETSENSE_VERIFY_PYTHON } else { Join-Path $root '.venv\Scripts\python.exe' }
    if (-not (Test-Path -LiteralPath $python)) { throw 'Existing Python environment required; this mode does not install dependencies.' }
    New-Item -ItemType Directory -Path (Join-Path $root 'tmp\verification') -Force | Out-Null
    $protected = @('config/prereg.yaml', 'results/prereg.lock', 'results/summary.json', 'results/primary_metrics.json', 'results/bootstrap.json', 'results/manifest.json', 'results/tuning.json', 'results/frontier.json')
    $before = @{}
    foreach ($name in $protected) { $before[$name] = (Get-FileHash -LiteralPath (Join-Path $root $name) -Algorithm SHA256).Hash }
    $prerequisites = @'
import importlib.metadata as metadata
import json
import sys
from fleetsense.common import ROOT, assert_lock, read_config, read_json, sha256
from fleetsense.data import raw_paths
assert sys.version_info[:2] == (3, 12)
assert_lock()
config = read_config()
for line in (ROOT / 'requirements.lock').read_text().splitlines():
    if line.strip():
        name, version = line.split('==')
        assert metadata.version(name) == version, name
for subset, path in raw_paths().items():
    assert sha256(path) == config['data']['raw_sha256'][subset], subset
assert sha256(ROOT / 'data/splits.json') == config['data']['splits_sha256']
summary = read_json(ROOT / 'results/summary.json')
assert summary['evaluation_kind'] == 'final_test'
assert read_json(ROOT / 'results/ui/summary.json') == summary
assert summary['study_design']['scope_warning']
print(json.dumps({'python': sys.version, 'dependency_lock_matches': True, 'raw_data_hashes_match': True, 'measured_ui_export_matches': True, 'run_id': summary['run_id'], 'verdict': summary['verdict']}))
'@
    $details = & $python -c $prerequisites
    if ($LASTEXITCODE) { throw 'Existing-results prerequisites failed.' }
    $testOutput = & $python -m pytest -q tests --basetemp=tmp/verification/pytest --junitxml=tmp/verification/tests.xml 2>&1
    $testsPassed = $LASTEXITCODE -eq 0
    $testOutput | Set-Content -LiteralPath (Join-Path $root 'tmp\verification\tests.txt')
    $testOutput | Write-Host
    $deckStatus = 'skipped by -SkipArtifacts'
    if (-not $SkipArtifacts) {
        if ((Test-Path -LiteralPath 'submission/assets/SIH2026-IDEA-Presentation-Format.pptx') -and (Test-Path -LiteralPath 'submission/assets/shot_policies.png')) {
            & $python submission/build_deck.py
            $deckStatus = if ($LASTEXITCODE -eq 0) { 'generated from existing measured summary and copied assets' } else { 'generation failed' }
        } else { $deckStatus = 'not generated: required assets missing' }
    }
    $after = @{}
    foreach ($name in $protected) { $after[$name] = (Get-FileHash -LiteralPath (Join-Path $root $name) -Algorithm SHA256).Hash }
    $preserved = @($protected | Where-Object { $before[$_] -ne $after[$_] }).Count -eq 0
    $report = [ordered]@{ scope = 'Existing-results smoke verification only; not full fresh pipeline reproduction'; full_reproduction = $false; primary_science_rerun = $false; started_utc = $started.ToUniversalTime().ToString('o'); smoke_wall_seconds = ((Get-Date) - $started).TotalSeconds; environment_reused = [bool]$env:FLEETSENSE_VERIFY_PYTHON; python_executable = $python; prerequisites = ($details | ConvertFrom-Json); tests_passed = $testsPassed; test_output = ($testOutput -join "`n"); deck = $deckStatus; protected_hashes_before = $before; protected_hashes_after = $after; protected_hashes_preserved = $preserved; passed = ($testsPassed -and $preserved -and $deckStatus -ne 'generation failed') }
    $report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $root 'results\reproduction_smoke.json') -Encoding utf8
    if (-not $report.passed) { throw 'Existing-results smoke verification failed; see results/reproduction_smoke.json.' }
    return
}
if (git status --porcelain) { throw 'Reproduction requires a clean checkout.' }
$runtime = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
if (-not (Test-Path -LiteralPath $runtime)) { $runtime = (Get-Command python).Source }
$version = & $runtime -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")'
if ($version -ne '3.12') { throw 'A Python 3.12 interpreter is required.' }
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) { & $runtime -m venv .venv; if ($LASTEXITCODE) { throw 'venv failed' } }
$python = Join-Path $root '.venv\Scripts\python.exe'
& $python -m pip install -r requirements.lock
if ($LASTEXITCODE) { throw 'Dependency installation failed.' }
& $python scripts\download_data.py
if ($LASTEXITCODE) { throw 'Data download failed.' }
& $python scripts\rebuild_dev_cache.py
if ($LASTEXITCODE) { throw 'Development cache rebuild failed.' }
& $python scripts\run_final_eval.py
if ($LASTEXITCODE) { throw 'Final evaluation failed.' }
& $python scripts\refresh_reports.py
if ($LASTEXITCODE) { throw 'Report and exploratory tradeoff refresh failed.' }
& $python -m pytest -q
if ($LASTEXITCODE) { throw 'Full validation failed.' }
if (-not $SkipArtifacts) {
    & $python scripts\capture_screens.py
    if ($LASTEXITCODE) { throw 'Capture failed.' }
    & $python submission\build_deck.py
    if ($LASTEXITCODE) { throw 'Deck failed.' }
    & $python scripts\record_demo.py
    if ($LASTEXITCODE) { throw 'Demo recording failed.' }
    & $python scripts\make_video.py
    if ($LASTEXITCODE) { throw 'Video generation failed.' }
    & (Join-Path $root 'submission\export_pdf.ps1')
    if ($LASTEXITCODE) { throw 'PDF export failed.' }
    & $python scripts\check_submission.py --allow-handoff-placeholders
    if ($LASTEXITCODE) { throw 'Submission validation failed for a reason other than user-supplied handoff placeholders.' }
}
