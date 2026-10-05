## 1


SMART INDIA HACKATHON 2026
Problem Statement ID - SIH26249
Problem Statement Title - Air Power - Predictive Maintenance & Fleet Availability
Theme - Transportation & Logistics
PS Category - Software
Team ID - [TEAM ID]
Team Name (Registered on portal) - Backpropagators
Ministry of Defence (MoD) / Defence Services Staff College
public simulated engine benchmark (NASA C-MAPSS); synthetic fleet scenario

## 2

FleetSense: Readiness Evidence for Predictive Maintenance
2
@SIH Idea submission- Template
Backpropagators


Proposed Solution
Serial-keyed engine health and maintenance history.
Calibrated failure risk at the policy's planning horizons.
Forecast, hard-time and condition rules share the same resources.
An independent checker audits every final schedule.
A locked study selects the verdict before adoption.


How It Addresses the Problem
Fragmented records: one serial-keyed history.
Reactive replacement: test a risk-based alternative.
Readiness: compare delivered flying as well as availability.
Decision trust: show uncertainty and losing scenarios.

REFUTED
Within the tested range, forecasting did not reach a worthwhile gain (upper 95% CI +0.3 pp < 1.0 pp). FleetSense caught this before deployment.
No development policy met the failure budget, so all used fewest-failures fallbacks; REFUTED concerns these frozen policies in tested scenarios, not forecasting in general.

Health + records

Risk horizons

Removal policy

Resource planner

Independent check

Readiness evidence
public simulated engine benchmark (NASA C-MAPSS); synthetic fleet scenario

## 3

TECHNICAL APPROACH
3
@SIH Idea submission- Template
Backpropagators


Technologies and Methodology
Python 3.12.14
pandas
LightGBM
scikit-learn
NumPy/SciPy
FastAPI
HTML/CSS/JS
offline Plotly
pytest


Untouched Evaluation Boundary
Dev: 140 engines in 4 engine-disjoint folds.
Final training: 105 engines; calibration: 35.
Test: 60 engines, unlocked only by the final entry point.


Working and Proposed Components
Solid pipeline: public-data import, inference, evaluation and dashboard.
Proposed adapters: read-only e-MMS and IMMOLS, subject to authorised interfaces.


Working Prototype
Source: {REPO_URL}
Demo: {VIDEO_URL}
public simulated engine benchmark (NASA C-MAPSS); synthetic fleet scenario

## 4

FEASIBILITY AND VIABILITY
4
@SIH Idea submission- Template
Backpropagators

63
Tests passed (includes UI)

180
Paired scenarios

0
Checker violations

1881.1 s
Evaluation wall time


Feasibility Analysis
Development failure budget 0.1 per aircraft-year: HT: 0/17 feasible; CT: 0/20 feasible; FC: 0/8 feasible. Registered fewest-failures fallback used for HT, CT, FC.
Thresholds were frozen from development results; test-frontier points are reporting-only, not new policy selections.
200 run-to-failure engines: 140 development, 60 held-out test.
18 operating cells and 10 common seeds; best simple rule is CT.


Potential Challenges and Mitigation
Authorised fleet data is unavailable: real-fleet validation remains future work.
Calibration shift: report subgroup reliability and decision-point error.
Automation overreach: provide evidence and explicit guardrails.
Deployment security controls remain requirements.


Viability
No cloud subscription is needed for this local prototype.
Reuse existing records through proposed read-only adapters.
Source: results/summary.json and locked preregistration. final-20261004T073432Z
public simulated engine benchmark (NASA C-MAPSS); synthetic fleet scenario

## 5

IMPACT AND BENEFITS
5
@SIH Idea submission- Template
Backpropagators


Potential Impact on the Audience
Maintenance planners: compare risk removal with tuned simple rules.
Readiness owners: inspect the availability / failure trade-off.
Procurement reviewers: retain a negative result before adopting a model.


Limits and Future Work
No development policy met the failure budget, so all used fewest-failures fallbacks; REFUTED concerns these frozen policies in tested scenarios, not forecasting in general.
Public simulated engines and synthetic fleet assumptions do not validate operational effectiveness.
Next study: a feasible development target and fresh held-out engines.


Generated Claim Ledger
Development tuning achieved the declared failure budget
Deviation
Forecast policy vs best simple policy: availability, failures, wasted life (public simulated benchmark, synthetic fleet)
Measured (final-20261004T073432Z)
Calibration of failure risk at the horizons the policy uses (untouched test engines)
Measured (final-20261004T073432Z)
Every schedule independently checked: no constraint violations
Measured (final-20261004T073432Z)
No future information reaches a policy (poisoned-future test)
Measured (final-20261004T073432Z)
Health history follows the engine serial across airframes
Deviation
Read-only adapters to e-MMS and IMMOLS
Proposed
Writing back work orders or spares demands
Future
Validation on real fleet data
Future
Access control, audit logging, signed updates, pinned dependencies, backups
Requirement
Identifying the physical fault behind a risk score
Not established
public simulated engine benchmark (NASA C-MAPSS); synthetic fleet scenario

## 6

RESEARCH AND REFERENCES
6
@SIH Idea submission- Template
Backpropagators
NASA C-MAPSS / Saxena and colleagues
Public simulated run-to-failure engines. Our fleet is a declared abstraction. Source
de Pater and Mitici
Prior integrated prognostics, repairable spares and shared maintenance slots. Integration alone is not our contribution. Source
LightGBM / Ke and colleagues
Gradient-boosted decision trees used for horizon-specific classifiers. Source
scikit-learn probability calibration
Isotonic calibration uses separate engines. Brier loss alone does not isolate calibration quality. Source
Romano, Patterson and Candes
CQR was considered and not used: interval coverage does not supply the failure CDF the policy queries. Source
Lufthansa Technik AVIATAR
Existing commercial predictive health analytics and maintenance planning. Our benchmark does not replace these services. Source
Airbus Skywise Core
Existing aircraft data integration and fleet-performance services. Field comparison remains future work. Source
Source: {REPO_URL}
Demo: {VIDEO_URL}
Preregistration: 0e227075f463
Data and integration limits are explicit.
public simulated engine benchmark (NASA C-MAPSS); synthetic fleet scenario