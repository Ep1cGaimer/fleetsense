# FleetSense

Readiness evidence before adopting predictive maintenance.

public simulated engine benchmark (NASA C-MAPSS); synthetic fleet scenario

## Registered result

Within the tested range, forecasting did not reach a worthwhile gain (upper 95% CI +0.3 pp < 1.0 pp). FleetSense caught this before deployment.

Every outcome is first-class: SUPPORTED requires the meaningful gain and every guardrail; REFUTED rules out the meaningful gain; INCONCLUSIVE is the remainder.

## Evidence

- Development failure budget 0.1 per aircraft-year: HT: 0/17 feasible; CT: 0/20 feasible; FC: 0/8 feasible. Registered fewest-failures fallback used for HT, CT, FC.
- Thresholds were frozen from development results; test-frontier points are reporting-only, not new policy selections.
- 200 run-to-failure engines: 140 development, 60 held-out test.
- 18 operating cells and 10 common seeds; best simple rule is CT.
- Calibrated risk at 8 horizons; training, calibration and evaluation engines are disjoint.
- Independent resource, duration, serial, failure-boundary and information-firewall checks.
- All thresholds selected globally on development simulations, not test outcomes.
- 63 tests passed; 0 independent-checker violations.
- 500 hierarchical engine-and-scenario resamples.

## Limitations

- No development candidate met the failure budget in any policy grid. The comparison uses fewest-failures fallbacks, not availability-optimal policies under a feasible budget; relative final guardrails do not establish absolute budget compliance.
- REFUTED applies to the frozen policies and tested scenario range, not to forecasting in general. No test retuning or replacement final policy is justified by the exploratory frontier.
- Exploratory Pareto points describe aggregate availability, failures and wasted-life tradeoffs only; they have no new uncertainty estimates or confirmatory status. Test engines are held out for selection but also used in the registered reporting-only frontier.
- Public simulated engine benchmark and synthetic single-engine fleet; not evidence for operational fleets.
- Overhaul is modelled as a new trajectory; spares, demand and turnaround are declared assumptions.
- Model evidence is not a physical diagnosis. Authorised e-MMS and IMMOLS adapters are proposed.
- Access control, signed updates and deployment assurance remain requirements.

## Reproduce

Run `scripts/reproduce.ps1` from a clean checkout. Raw data and model caches are ignored; locked configuration, split hashes and result manifests are committed.

## Local UI

Run `.venv/Scripts/python.exe -m app.server`, then open the loopback address printed by the server. No model computation happens in the server. Every chart reads exported evidence only.

See `PREREGISTRATION.md`, `DECISIONS.md`, `DEVIATIONS.md`, `CLAIMS.md`, `app/ui/DATA.md`, and `results/manifest.json`.

Submission links remain `{REPO_URL}` and `{VIDEO_URL}` until the user supplies them. No remote is configured and nothing is pushed.

## Outcome templates

These are templates, not additional findings:

- SUPPORTED: On a public simulated engine benchmark, calibrated forecasting raised fleet availability by {dA:.1f} pp (95% CI {lo:.1f} to {hi:.1f}) over the best tuned simple rule, with all declared guardrails met.
- INCONCLUSIVE: Forecasting changed availability by {dA:+.1f} pp (95% CI {lo:+.1f} to {hi:+.1f}): not enough evidence yet to justify it. FleetSense shows this before money is spent.
- REFUTED: Within the tested range, forecasting did not reach a worthwhile gain (upper 95% CI {hi:+.1f} pp < {minimum:.1f} pp). FleetSense caught this before deployment.
