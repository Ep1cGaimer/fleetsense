# Registration and evaluation boundary

The authoritative constants, models, split seed, parameter grids, operating cells, bootstrap protocol and verdict rule live in `config/prereg.yaml`. Engine IDs are saved in `data/splits.json`; its content hash is incorporated before locking.

All development forecasts are engine-disjoint out-of-fold predictions. Sensor filters, scalers, regressors and classifiers are fitted on the corresponding training engines only. Isotonic maps are fitted on the separate calibration engines. Threshold tuning sees development simulations only.

`scripts/lock_prereg.py` freezes the complete configuration after development tuning and a runtime-only hierarchical simulation dry run. Its dedicated commit precedes any test access. `scripts/run_final_eval.py` rejects a mismatched hash, changed split or dirty checkout, runs required core tests, and is the only production script that sets the test-loader unlock variable.

The primary experiment pairs every locked scenario across hard-time, condition-threshold, calibrated-forecast and explicitly privileged oracle policies. Uncertainty resamples test engines, then reruns common-draw scenarios. The frontier is secondary reporting only, never a new test-time selection.

Daily order: shop returns, release completed maintenance, evaluate requests, planner starts, flight and failures, end-of-day completion. Duration includes the start and completion days; serviceability resumes the next morning. Failure days receive no aircraft-day availability credit. Pending planned requests continue flying and can become unplanned failures.

The independent checker imports neither simulator nor planner. It reconstructs inventory, aircraft states and cycles from events and obtains failure limits from parsed raw train files. Required mutation tests are not replaced by simulator self-checks.

Waste ratio uses the mean per planned removal, pooled across removals, rather than an unweighted mean of scenario means. A zero baseline denominator is undefined and fails that guardrail. No interval of engine risk is called a coverage certificate.

The complete locked experiment writes `results/summary.json`, `results/manifest.json`, independent checked event files, bootstrap distributions, calibration populations, reporting frontier, figures and static UI exports. Missing evidence prevents a successful run; development outputs never masquerade as final results.

Every actual change after lock is recorded in `DEVIATIONS.md`; registered constants are not silently edited.
