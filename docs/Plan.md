# Plan.md
## 1. Purpose and Scope
This round only creates `Plan.md` from the provided authoritative documents and dataset evidence. `task.md` is not created yet. No code implementation is performed yet.  
Scope of this plan is to define an execution-ready direction for an explainable educational QA system that is compliant with runtime input constraints, open-source model rules (`<=8B`), and evaluation expectations for answer correctness, explanation quality, and reasoning depth.

## 2. Source Documents and Dataset Basis
Primary sources of truth:
- `docs/flow.md` (authoritative system/runtime flow and constraints)
- `docs/competition.md` (authoritative competition rules and submission expectations)
- `report_past.md` (dataset-grounded evidence and hard-case requirements)

Optional guidance files status:
- `review.json`: present and applied (status: `needs_revision`, blocking issue `ISSUE_CHOICES_RUNTIME_SCHEMA`)
- `dataset_answer.md`: present and applied (A0 clarification adopted)

Dataset basis used from `report_past.md`:
- Current local dataset snapshot: `411` records, `808` questions
- Answer classes observed: `Yes/No`, `Unknown`, `A/B/C/D`
- Documented hard/edge cases include numeric-temporal long chains, symbolic options, nonstandard `choices` option source, and annotation inconsistencies.

## 3. Planning Assumptions
- Runtime inference only consumes `premises-NL` and `question`; reference fields (`premises-FOL`, `answers`, `explanation`, `idx`) are offline-only for validation/evaluation.
- Model calls use `.env` configuration (`SHOPAIKEY_BASE_URL`, `SHOPAIKEY_API_KEY`, `SHOPAIKEY_MODEL`, and generation controls), with model constrained to open-source `<=8B` (current local identifier in flow doc: `qwen2.5-7b-instruct`).
- Explainability is mandatory per competition rules; explanation must be grounded in actual reasoning trace, not free-form unsupported generation.
- Symbolic engine use is encouraged but not mandatory in competition; flow doc explicitly prescribes symbolic verification routes, so plan keeps that flow.
- Dataset-version mismatch risk (`competition` text vs local file size) is tracked as an evaluation/reporting concern, not a runtime blocker.

## 4. Dataset Coverage Summary
Coverage targets are derived from the observed distribution and case taxonomy in `report_past.md`:
- Core task families:
  - Yes/No/Unknown reasoning
  - MCQ option selection (`A/B/C/D`)
  - Open-ended best-effort reasoning
- Logic phenomena to support:
  - Entailment/contradiction
  - Negation polarity preservation
  - Conjunction/disjunction branches
  - Conditional/implication queries
  - Multi-hop chains across many premises
- Specialized content to support:
  - Numeric thresholds, percentages, GPA/credits/time-window constraints
  - Symbolic/FOL-like tokens in question/options
  - Entity-linking/coreference sensitivity in long questions
- Data anomalies to tolerate without runtime collapse:
  - Premise-count mismatch between NL/FOL annotations
  - Answer/explanation conflict signals
  - Option-format inconsistency (`inline` vs `choices` field)

## 5. Required Case Coverage
The implementation plan that follows must explicitly cover all high-priority `report_past.md` requirements:
- `CR-001`: Flatten raw records to per-question runtime-safe samples while preserving local IDs.
- `CR-002`: Candidate extraction from inline options, with optional raw `choices` normalized into canonical inline `A./B./C./D.` question lines during flattening.
- `CR-003`: Native decision policy for `Yes/No/Unknown` and MCQ `A/B/C/D`.
- `CR-004`: Numeric/comparison/temporal reasoning path with deterministic evaluation.
- `CR-005`: Preserve and verify negation, conjunction/disjunction, and conditional structure.
- `CR-007`: Dataset anomaly/QC tagging and conflict-aware reporting without hard-failing runtime.
- `CR-008`: Strong abstention/`Unknown` policy for insufficient evidence.

Medium-priority but required for robustness:
- `CR-006`: Symbolic-token-aware parsing path for FOL-like question/option content.

Hard cases from `report_past.md` are mandatory in validation slices:
- `record=34,q=0` numeric + temporal + long-chain constraints
- `record=132,q=0` `choices`-field MCQ extraction
- `record=333,q=0` symbolic MCQ options
- `record=37,q=1` answer/explanation conflict handling
- `record=376-382` premise-count mismatch resilience

## 6. Proposed System Flow
Flow follows `docs/flow.md` sequence, with no unsupported architecture added:
1. Raw dataset -> flatten to one sample/question for local evaluation.
2. During flattening, if a record has separate `choices`, merge them into the `question` text as canonical stable `A./B./C./D.` lines (ordered and deterministic), then persist only the normalized question text for inference.
3. Runtime-safe input shaping (allow only runtime fields in inference path; no runtime `choices` field).
4. Async sample worker with bounded concurrency, retry, timeout, failure isolation, and deterministic output ordering.
5. Premise parse-frame extraction with cache:
   - local evaluation key: `record:<record_id>`
   - API key: `premises_hash:<normalized premises + versioning>`
   - single-flight locking for concurrent same-key requests.
6. Frame validation -> deterministic frame-to-AST compilation (LLM does not directly emit final AST).
7. Candidate extraction (MCQ or claim-based paths), then candidate frame extraction and AST compilation.
8. AST validation/normalization and numeric feature detection.
9. Verification routing (Horn/contraposition, numeric evaluator, bounded quantifier handling, Z3 path where grounded and supported).
10. Proof/debug trace construction.
11. Output formatting to required API schema with optional evidence fields.

## 7. Data Handling Plan
- Input handling:
  - Keep raw dataset untouched.
  - Generate and consume flattened local-eval artifact for one-question-per-sample processing.
  - Flattening canonicalization rule: if raw record contains separate `choices`, serialize them into canonical stable `A./B./C./D.` lines appended to `question` before inference; do not add `choices` as a runtime input field.
- Runtime-safe field discipline:
  - Inference path reads only `premises-NL`, `question`, plus local IDs for local evaluation orchestration (`sample_id`, `record_id`, `question_id`).
  - Runtime schema remains `premises-NL + question` for API parity; local IDs are local-eval metadata only.
  - Any reference-only fields are excluded by sanitizer and guarded by tests/checks.
  - Sanitizer must verify that MCQ-labeled answers (`A/B/C/D`) have extractable options from flattened `question`; missing options must emit warning/error artifacts and root-cause tags (not silent pass-through).
- Caching discipline:
  - Separate local-eval and API cache key strategies exactly as required by flow doc.
  - Include parser prompt/compiler version in cache fingerprint to prevent stale semantic reuse.
- Logging/artifacts discipline:
  - No `.env` secrets, auth headers, or raw secret-bearing URLs in logs.
  - Maintain parser lifecycle artifacts, numeric failure artifacts, and stage-attributed root-cause traces.
- Dataset anomaly handling:
  - Emit QC flags/metrics for mismatches/conflicts.
  - Emit explicit artifacts for MCQ option-missing anomalies after flattening/canonicalization.
  - Continue processing unless runtime input is structurally unusable.

## 8. Reasoning / Solving Strategy
- Parsing strategy:
  - LLM generates compact parse frames (`rule`, `fact`, `claim`, `compound`, `ambiguous`) under strict schema.
  - Deterministic compiler transforms validated frames into typed AST; ambiguous/lossy frames are rejected, not guessed.
- Logical strategy:
  - Entailment/contradiction checks over compiled ASTs with explicit negation support.
  - Quantifier support via schema-level matching and bounded instantiation over discovered constants.
- Numeric strategy:
  - Numeric slots (`numeric_value`, `numeric_condition`, `arithmetic_expression`) extracted in frame stage.
  - Deterministic numeric evaluator enforces unit/range/tolerance checks and provides derived facts to solver context.
- Routing strategy:
  - Prefer minimal-capability route that can prove/refute safely.
  - Use Z3 for grounded numeric/non-Horn fragments when needed by routed AST shape, not by hardcoded dataset patterns.
- Fallback strategy:
  - Unsupported or low-confidence cases return `Unknown` (or submission alias mapping when needed), with explicit reason and confidence penalty.

## 9. Output Format Plan
Required API response fields:
- `answer`
- `explanation`
- `fol`
- `cot` (trace verbalization, not free-form invented reasoning)
- `premises` (used premise references)
- `confidence`

Policy notes:
- Explanation must be proof-trace-grounded and premise-cited.
- Numeric answers/explanations must include computed values and their premise provenance.
- MCQ forced-choice adapter (if evaluator requires no `Unknown`) must preserve internal decision trace and confidence penalties in debug artifacts.

## 10. Validation Plan
- Contract validation:
  - Runtime input contract tests ensure only `premises-NL` + `question` are required.
  - Output contract tests ensure mandatory response fields always exist.
  - Flattening contract tests ensure any separate raw `choices` are merged into canonical `A./B./C./D.` lines in `question` before inference.
  - MCQ contract checks ensure options remain extractable from flattened `question`; failures generate warning/error artifacts.
- Parser/compiler validation:
  - Strict frame schema checks and rejection paths for lossy/ambiguous outputs.
  - AST validation for node contracts, metadata presence, variable binding, arity stability, and direction/polarity integrity.
- Runtime behavior validation:
  - Async concurrency/timeout/retry behavior and single-flight cache correctness.
  - Earliest-failure-stage attribution integrity in debug traces.
  - Record `132`-style regression validation is required to prevent silent option loss when raw options originate from separate `choices`.
- Security/config validation:
  - Live LLM connectivity smoke test from `.env`, with secret redaction.
  - Live parse-frame smoke/quality gate once parser path is wired.
- Open-ended validation:
  - Add a focused best-effort validation note: verify open-ended responses are synthesized only from grounded proof-trace facts; otherwise return `Unknown` with low confidence and explicit fallback reason.

## 11. Evaluation Plan
- Metrics:
  - Answer correctness by question family (`Yes/No/Unknown`, MCQ, open-ended).
  - Explanation grounding quality (premise citation and trace consistency checks).
  - Reasoning depth proxies (proof steps, derived facts, optional evidence completeness).
- Slice-based evaluation:
  - Hard-case slices from `report_past.md` must be evaluated separately and tracked.
  - Numeric/temporal slice, symbolic-token slice, anomaly/noise slice, option-format slice (including record `132`-style `choices` canonicalization), and open-ended best-effort slice.
- Error analysis:
  - Root-cause category distribution per flow-defined taxonomy.
  - Include MCQ option-missing post-flattening counts and associated stage attribution.
  - Separate model failures from annotation-noise-flagged cases.
- Reproducibility:
  - Record dataset version metadata and model/config fingerprints in evaluation artifacts.

## 12. Risks and Mitigations
- Risk: Parser fragility on mixed NL + symbolic + long clauses.
  - Mitigation: strict schema, repair loop, ambiguous-class rejection, parser replay artifacts.
- Risk: Numeric/temporal misinterpretation causes high-impact answer errors.
  - Mitigation: dedicated numeric slots, deterministic evaluator, strict validation gates.
- Risk: Candidate loss from inconsistent MCQ formatting.
  - Mitigation: flatten-time canonicalization of any raw `choices` into stable inline `A./B./C./D.` lines, plus post-flattening extractability diagnostics/artifacts.
- Risk: Annotation inconsistency distorts evaluation conclusions.
  - Mitigation: conflict-aware reporting/QC flags, separate clean vs noisy slice metrics.
- Risk: Runtime rule violations (reference-field leakage or closed-source model drift).
  - Mitigation: sanitizer guards, runtime field-access tests, `.env` model-source enforcement.
- Risk: Performance instability under async load.
  - Mitigation: bounded concurrency, timeouts, retries with backoff/jitter, failure isolation.

## 13. Open Questions
- Confirm official competition test-set version and whether local `411/808` snapshot differs from release baseline used for ranking.
- Confirm final submission-time label policy for unresolved MCQ/Unknown cases (whether forced A/B/C/D is mandatory).
- Confirm exact judging rubric weights for P1/P2/P3 once published.
- Confirm acceptable optional evidence fields in final API schema if workshop updates occur.

## 14. Approval Readiness Checklist
- [x] Plan is grounded in `docs/flow.md`, `docs/competition.md`, and `report_past.md`.
- [x] This round explicitly creates only `Plan.md`; no `task.md`, no code implementation.
- [x] Runtime-safe input constraints and reference-field restrictions are explicitly enforced.
- [x] Open-source `<=8B` LLM constraint and `.env` model-source rules are included.
- [x] Required API response fields and optional evidence strategy are defined.
- [x] All high-priority `report_past.md` coverage requirements are addressed.
- [x] All listed hard cases are included in required validation slices.
- [x] Validation, evaluation, risks, and mitigations are defined for downstream task decomposition.
