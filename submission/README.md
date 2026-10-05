# Submission bundle

The portal PDF, editable deck, plain-text mirror and automated demo are generated from the locked evaluation result. No measured headline is manually entered into the slides.

Artifact scripts are generated snapshots of the single authoritative `sih-2026/tooling` source. Do not edit these copies. Their content hashes are checked against `toolkit_manifest.json`; the standalone snapshots keep this repository independently reproducible.

Run these commands from the repository root using its virtual environment:

```powershell
.venv\Scripts\python.exe scripts\capture_screens.py
.venv\Scripts\python.exe submission\build_deck.py
powershell -ExecutionPolicy Bypass -File submission\export_pdf.ps1
.venv\Scripts\python.exe scripts\record_demo.py
.venv\Scripts\python.exe scripts\make_video.py
.venv\Scripts\python.exe scripts\check_submission.py
```

Before publication, the submission check deliberately reports the missing team ID, source URL and demo URL. Supply those after authenticating GitHub, choosing the repositories and uploading the videos:

```powershell
.venv\Scripts\python.exe submission\build_deck.py --team-id "REGISTERED_ID" --repo-url "PUBLISHED_SOURCE_URL" --video-url "UNLISTED_VIDEO_URL"
powershell -ExecutionPolicy Bypass -File submission\export_pdf.ps1
.venv\Scripts\python.exe scripts\check_submission.py
```

No remote is created and nothing is uploaded automatically. The team leader checks the live SIH problem-statement capacity before uploading the generated PDF. The official template, fonts and Lucide icon assets are retained from the supplied references. The deck builder validates the preregistration hash and requires a completed verdict and a working-dashboard screenshot.
