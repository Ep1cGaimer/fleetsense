# Decisions before locking

| Decision | Alternative | Reason |
|---|---|---|
| Use bundled Python 3.12.14 to create the project venv. | Launcher 3.11 or 3.14. | `py -3.12` is unavailable, but the bundled interpreter exactly meets the requested minor version. |
| Use the configured git identity; omit an attribution trailer. | Invent an attribution line. | No attribution line was supplied by the system. |
| One common seeded trajectory stream, initial-age fractions, and full demand array per scenario. | Policy-specific randomness. | Draw consumption can differ after policy actions, but the underlying draws and demand are paired. |
| Changes start in the morning; failure is observed after flying, queued for the next morning. | Same-day replacement after failure. | Avoid optimistic same-day rescue. |
| Maintenance occupies start through start + D - 1, inclusive; return to service is next morning. A failure day counts unavailable even if some cycles were flown. | Completion-day serviceable or partial-day availability. | Explicit inclusive downtime, no optimistic aircraft-day credit. |
| At cycle zero use risk zero and health one, with no lookup of cycle-one rows. | Read the first row from the future. | Preserve the information firewall. |
| Wasted-life guardrail is undefined and not met if the baseline has no planned removals. | Treat zero denominators as success. | Fewer claims. |
| Best simple selection uses feasibility first, then availability; if both are infeasible, failures first. | Choose a high-availability rule exceeding budget. | Apply the declared tuning budget consistently. |
| Frontier uses all final scenario seeds and is reporting-only. | Select a new threshold on test. | Keep threshold choice entirely in dev. |
| SUPPORTED text says 'all declared guardrails met' unless both observed failure difference and its upper CI are nonpositive. | Always say 'no more unplanned failures'. | The positive allowed failure margin does not establish no increase. |
| Contrast-model Brier differences are reported in their observed direction, never assumed inflated. | Presume a leakage contrast must improve. | The experiment determines the result. |
| Choose bootstrap count using a dev-only benchmark of the actual hierarchical simulation workload. | Reduce constants after seeing test outcomes. | Runtime-only pre-lock decision. |
| P2 twin-engine and CP-SAT studies are out of scope for this implementation. | Add optional studies before required evidence. | Prioritize the complete registered core experiment. |
| UI uses Sovereign neutral-dark tokens and local fonts; aircraft-state strip is the distinctive visual anchor. | Decorative gradients and generic KPI landing page. | Evidence-first operations console, with restrained blue navigation and Okabe–Ito plots. |

Per-fold sensor lists and runtime measurement are appended before lock.

## Artifact retention

Full primary, hierarchical-bootstrap and reporting-frontier event, firewall and scenario logs are retained locally in ignored `results/runs/`. The committed manifest records their file count, total bytes and deterministic aggregate content hash. Compact final test tables, distributions, primary metrics, summaries, figures and UI JSON are committed. This avoids committing a large raw-log directory without reducing any registered measurement or checker execution.

Browser smoke tests may use a visibly named synthetic fixture before final UI exports exist. They measure routing and rendering only, never the scientific claim. Final smoke tests use the actual final exports.

## User-supplied submission identifiers

Team identity and source/video URLs are unknown until handoff and are not measurements. The main implementation records CLI-supplied identifiers in its generated submission build manifest and exempts only those identity/link digits from its numeric-provenance check. Scientific figures and study constants remain summary-derived; placeholders continue to block completed submission.

## Observed training-only sensor selection

- fold0: s2, s3, s4, s6, s7, s8, s9, s10, s11, s12, s13, s14, s15, s17, s20, s21.
- fold1: s2, s3, s4, s6, s7, s8, s9, s10, s11, s12, s13, s14, s15, s17, s20, s21.
- fold2: s2, s3, s4, s6, s7, s8, s9, s10, s11, s12, s13, s14, s15, s17, s20, s21.
- fold3: s2, s3, s4, s6, s7, s8, s9, s10, s11, s12, s13, s14, s15, s17, s20, s21.

Actual lists are used; differences from the expected list exist.

## Dev-only runtime decision

Measured 4 hierarchical replicates in 5.586 seconds; estimated 500-replicate workload 698.226 seconds. Locked bootstrap count: 500. The timing benchmark includes simulator, independent checker and event serialization. No test engines were accessed.

## Final training sensor list before lock

s2, s3, s4, s6, s7, s8, s9, s10, s11, s12, s13, s14, s15, s17, s20, s21. Selected on final training dev folds only, without test access.

## Checkout byte preservation after locking

A fresh detached checkout with LF conversion correctly failed the raw-byte preregistration hash guard before any test access. A new ordinary Windows checkout restored the exact original CRLF bytes and matched both prereg and split hashes. Explicit Git attributes now preserve those original byte formats in future checkouts. No locked configuration byte, value, split or hash was changed. Vendored Plotly bytes are also preserved rather than line-ending converted.

Core reproduction is tested independently from submission artifacts, with cached pinned dependencies and verified raw data. Its measured wall time is logged separately, never labelled as a full submission reproduction duration.
