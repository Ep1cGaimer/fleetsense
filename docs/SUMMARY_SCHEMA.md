# Summary contract — schema version 1

`results/summary.json` is emitted only by the locked final evaluation. Smoke and dev output cannot occupy this path.

Top-level keys:

* `schema_version`, `project`, `problem_id`, `run_id`, `evaluation_kind` (always `final_test`), `prereg_sha256`, `prereg_commit`, `git_commit`, `data_labels`.
* `verdict` (`SUPPORTED`, `INCONCLUSIVE`, `REFUTED`), `verdict_text`, `best_simple`, `selected_parameters`.
* `primary`: `delta_availability_pp`, `ci95_pp` (lower, upper array), `minimum_gain_pp`, `paired_scenarios`, `bootstrap_replicates`.
* `guardrails`: `failures` (`delta`, `ci95`, `limit`, `met`); `wasted_life` (`ratio`, `ci95`, `limit`, `met`); `flying_delivered` (`delta_pp`, `ci95_pp`, `limit_pp`, `met`). Undefined ratios are null and fail their guardrail.
* `policy_metrics`: object keyed by `HT`, `CT`, `FC`, `OR`, each with `availability`, `availability_pct`, `failures_per_aircraft_year`, `planned_per_aircraft_year`, `wasted_life_cycles`, `flying_delivered`, `reuse_events`, `cap_events`.
* `counts`: `engines`, `dev_engines`, `test_engines`, `folds`, `horizons`, `cells`, `paired_scenarios`, `policy_runs`, `bootstrap_policy_runs`, `frontier_policy_runs`, `tests_passed`, `checker_mutations_caught`, `checker_mutations_total`.
* `checker_violations` (zero for a successful run), `audits` (leakage, poisoned_future, mutations, sensitivity, horizon, scale, manifest), `calibration`, `cells`, `frontier`, `manifest`.
* `presentation`: `constants` (all numeric prereg leaves and reference years), `counts` (copy of counts), `allowed_numbers` (numeric-token strings derived recursively from the complete summary plus formatted variants), `python_version`, `data_labels`, `verdict_templates`, `guardrail_wording`, `wall_seconds`.

Compatibility aliases: `delta_availability_pp`, `ci95`, `tests_passed`, `paired_scenarios`, `bootstrap_replicates`, `wall_seconds`, `dataset`.

Main integration: `data_label` is the joined data labels. `presentation` also includes `headline`, `metrics` (label/value/source JSONPath), `facts`, `limitations`, `stack`, `data_boundary`, `allowed_constants` and exact outcome `verdict_templates`. Top-level `claims` is an array of claim/status/evidence rows. `manifest.tests` has passed/failed plus separately counted core and production-UI passes. Raw checked logs are kept in an ignored local archive with aggregate content digest and byte/file counts in the manifest. `results/test_tables.parquet` retains the compact final table in Git.

`results/ui/` contains `summary.json`, `policies.json`, `calibration.json`, `replay.json`, `audits.json`, `claims.json`, `engine.json`. These are same-origin static exports with `schema_version`, `run_id` and `data_labels`. Plot JSON is serialized numeric series, not HTML. Replay contains `days`, `events`, `scenario`, `checker_violations`; every day contains aircraft serial, trajectory, cycle, status and risk. Engine detail is evaluation-only model evidence, not diagnosis.

Main owns submission and capture tooling. This contract is stable before those tools are written.
