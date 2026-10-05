# SIH portal fields — SIH26249 (Ministry of Defence)

## Problem Statement

SIH26249 — Air Power - Predictive Maintenance & Fleet Availability (Transportation & Logistics · Software)

## Idea title

FleetSense: Fleet Readiness and Predictive Maintenance Console

## Idea description — short (≈ 500 characters)

FleetSense is an on-premise readiness console for an air squadron. It joins engine health data, maintenance records and spares stock per airframe, gives every engine a calibrated failure risk at 10–100 cycle horizons, and plans engine removals against real slot and spare limits. A policy lab tests maintenance rules on a simulated squadron-year before adoption, and an independent rule checker re-verifies every schedule. Open source, air-gapped, CPU only.

## Idea description — long (≈ 1,500 characters)

Aircraft availability suffers when maintenance is reactive and data is scattered across health monitoring, technical records, spares and maintenance agencies. CAG found Su-30MKI serviceability at 55–60% against a 75% norm, and the IAF fields 31 fighter squadrons against 42 sanctioned, so every available airframe counts.

FleetSense brings this together in one console that runs entirely on base servers:
1) Fleet board: every airframe, its installed engine and the calibrated risk that the engine fails within the next 20 cycles, with spares and overhaul status.
2) Engine health: sensor trends compared with healthy engines of the same age, and failure risk across planning horizons.
3) Removal planner: books engine changes against maintenance slots, crews and spare engines.
4) Policy lab: compares fixed-interval, condition-based and predictive maintenance on the same simulated squadron before any rule is adopted.
5) System checks: an independent rule engine re-verifies every schedule.

Working prototype (NASA C-MAPSS engines, simulated squadron): failures flagged in advance 86.5% of the time on engines the model never saw; predictive removal gave the highest availability of the three rules with 11% less engine life wasted; 0 rule violations across 44,820 simulated squadron-years; 200 airframes simulated for a year in 0.64 s; 63 automated tests. Built with LightGBM, scikit-learn and FastAPI, designed to read e-MMS and IMMOLS exports through read-only adapters.

## Keywords

SIH26249, predictive maintenance, fleet availability, Indian Air Force, engine health, remaining useful life, spares planning, LightGBM, calibration, on-premise, air-gapped
