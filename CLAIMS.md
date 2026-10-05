# FleetSense claim ledger

Generated from locked final run `final-20261004T073432Z`.

| Claim | Status | Evidence |
|---|---|---|
| Development tuning achieved the declared failure budget | Deviation | results/tuning.json: no HT, CT or FC candidate met the budget; all used the registered fewest-failures fallback. This is not availability maximisation under a feasible budget. |
| Forecast policy vs best simple policy: availability, failures, wasted life (public simulated benchmark, synthetic fleet) | Measured (final-20261004T073432Z) | primary; guardrails |
| Calibration of failure risk at the horizons the policy uses (untouched test engines) | Measured (final-20261004T073432Z) | calibration |
| Every schedule independently checked: no constraint violations | Measured (final-20261004T073432Z) | checker_violations |
| No future information reaches a policy (poisoned-future test) | Measured (final-20261004T073432Z) | audits.poisoned_future |
| Health history follows the engine serial across airframes | Deviation | Only lifecycle-instance removal and installation traces are demonstrated. Overhaul creates a new serial; physical-component continuity across overhaul or airframes is not established. |
| Read-only adapters to e-MMS and IMMOLS | Proposed | Subject to authorised interface specification |
| Writing back work orders or spares demands | Future | Not implemented |
| Validation on real fleet data | Future | Public simulated benchmark only |
| Access control, audit logging, signed updates, pinned dependencies, backups | Requirement | Production requirements; not a security certification |
| Identifying the physical fault behind a risk score | Not established | Evidence view shows model evidence only |
