# Study design review: infeasible development target

This is a post-result disclosure, not a preregistration amendment. The locked
configuration, selected policies, measured statistics and REFUTED verdict remain
unchanged. The declared development budget is 0.1 unplanned failures per
aircraft-year. Existing `results/tuning.json` contains:

| Policy | Feasible / candidates | Lowest failure rate | Frozen parameter |
|---|---|---|---|
| HT | 0 / 17 | 0.2916666666666667 | 100 |
| CT | 0 / 20 | 0.27314814814814814 | 0.4 |
| FC | 0 / 8 | 0.26944444444444443 | 0.02 |

Selection was implemented in `scripts/run_dev.py` and
`fleetsense/statistics.py::select_parameter`; there is no
`scripts/tune_policies.py` in this checkout. All three grids exhausted the budget
constraint and invoked the registered fewest-failures fallback. Thus the final
comparison is not availability maximisation under a feasible failure budget.
Meeting relative final guardrails does not establish absolute budget compliance.
The fixed claim ledger labels the unmet tuning target **Deviation**; invoking a
registered fallback was not itself an unregistered procedural change.

## Exploratory tradeoffs only

Run `.venv/Scripts/python.exe scripts/exploratory_tradeoffs.py` to produce
`results/exploratory_tradeoffs.json` from the existing development tuning and
registered reporting-only test frontier. It records source hashes, per-policy
candidate and feasible counts, and both pooled and per-policy nondominated points.
The two-objective frontier maximises availability and minimises failures; the
three-objective frontier additionally minimises wasted life. Equal objective
values are retained. Missing wasted-life values are excluded only from the
three-objective frontier and counted explicitly.

These are aggregate point-estimate tradeoffs, not recommended policies, new
uncertainty estimates or confirmatory findings. Test-frontier descriptions must
not inform threshold selection, test retuning or a replacement final policy.
There are no simulations, model fits or bootstrap reruns in this script. Dev
dry-run timing and its few resamples are not final evidence. Archived per-run dev
tuning outputs are not present in this checkout; this analysis uses the retained
actual aggregate tuning table, not reconstructed or invented runs.

REFUTED applies only to the frozen policies and tested synthetic scenarios, not
forecasting generally or all possible thresholds. Grid infeasibility does not
prove universal infeasibility. Public simulated engines, synthetic single-engine
fleet dynamics and assumed overhaul/spares/demand limit operational interpretation.
Any future budget or grid redesign needs a separately declared study and fresh
held-out evaluation; it cannot repair this outcome retrospectively.

`scripts/refresh_reports.py` regenerates reporting metadata, claim ledger,
presentation facts/limitations, static UI exports and README from the existing
measured summary. It preserves measured fields and the exact verdict. Media
artifacts remain the main coordinator's responsibility.
