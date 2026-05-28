# Implementation Task Plan
## 1. Purpose
This document is the execution contract for future implementation agents. It translates `docs/Plan.md` into ordered, batch-based work for the EXACT 2026 explainable educational QA system.

Execution must happen one batch at a time. Future agents must not skip validation, weaken runtime input constraints, leak reference annotations into inference, or replace live LLM validation with mocks.

## 2. Authoritative Inputs
- Primary approved plan: `docs/Plan.md`, especially sections 3-12 and 14.
- Runtime and architecture constraints: `docs/flow.md`, especially Goal, High-Level Flow, Runtime Pipeline, Parse Frames Before AST, Numeric Frame Extraction, Frame-to-AST Compilation, Candidate Extraction, Symbolic Verification, Answer Decision, Explanation Generation, Debug Trace, Maintainability Checkpoints, and Recommended Build Order.
- Competition rules and submission expectations: `docs/competition.md`, especially Competition Rules, Dataset Type 1, Evaluation Criteria, Test Format, and Submission Requirements.
- Dataset evidence: `docs/report_past.md`, especially Dataset Overview, Dataset Case Taxonomy, Hard / Edge Cases, Coverage Requirements, Architecture Risks, and Recommended Planning Guidance.
- Clarification source: `docs/dataset_answer.md`, especially Answer and Recommended Plan.md Revision for separate `choices` handling.

Key source anchors:
- `.env` model and live smoke requirements: `docs/flow.md:12`, `docs/flow.md:168`, `docs/flow.md:176`.
- Runtime input and API shape: `docs/flow.md:102`, `docs/flow.md:133`.
- Async/cache requirements: `docs/flow.md:186`.
- Frame and AST architecture: `docs/flow.md:234`, `docs/flow.md:435`.
- Numeric reasoning: `docs/flow.md:354`.
- Candidate extraction and decision policy: `docs/flow.md:472`, `docs/flow.md:574`.
- Explanation and debug trace: `docs/flow.md:605`, `docs/flow.md:615`.
- Dataset coverage and hard cases: `docs/report_past.md:2`, `docs/report_past.md:18`, `docs/report_past.md:35`, `docs/report_past.md:83`.
- Approved plan coverage requirements: `docs/Plan.md:49`.

## 3. Approved Plan Summary
Approved runtime flow:

```text
raw records
-> flattened one-question samples
-> runtime-safe input: premises-NL + question
-> shared .env-based LLM client
-> bounded async worker with retry, timeout, and cache
-> premise parse frames from LLM
-> strict frame validation
-> deterministic frame-to-AST compiler
-> candidate extraction and candidate ASTs
-> AST validation, normalization, numeric feature detection
-> symbolic and numeric verification
-> proof/debug trace
-> answer, explanation, fol, cot, premises, confidence
```

The system must use only `premises-NL` and `question` at runtime. Reference fields such as `premises-FOL`, `answers`, `explanation`, and `idx` may be used only for offline validation, scoring, training analysis, and error reporting. All LLM calls must use the `.env`-configured open-source model with 8B parameters or fewer. Closed-source models are prohibited.

The LLM is the semantic parser, not the final solver. It emits compact parse frames. Code validates those frames, compiles them into typed ASTs, routes numeric and symbolic verification, and generates proof-trace-grounded explanations.

## 4. Dataset Coverage Requirements
Implementation and validation must cover the local dataset evidence:
- Current local snapshot: 411 records and 808 questions (`docs/report_past.md:5`, `docs/report_past.md:7`).
- Answer families: Yes/No, Unknown, and MCQ A/B/C/D (`docs/report_past.md:11`).
- `CR-001`: flatten multi-question raw records to per-question runtime-safe samples.
- `CR-002`: normalize separate raw `choices` into canonical inline `A./B./C./D.` question lines during flattening; do not pass `choices` as runtime input.
- `CR-003`: support native Yes/No/Unknown and MCQ A/B/C/D decision policies.
- `CR-004`: support numeric, comparison, and temporal reasoning through deterministic evaluation.
- `CR-005`: preserve negation, conjunction/disjunction, and conditionals.
- `CR-006`: support symbolic-token-aware parsing for FOL-like question or option content.
- `CR-007`: tag dataset anomalies and QC issues without hard-failing usable runtime samples.
- `CR-008`: implement strong Unknown/insufficient-evidence abstention logic.

Required validation slices must include:
- `record=34,q=0`: numeric, temporal, entity, and long-chain reasoning.
- `record=132,q=0`: separate `choices` source merged into question text.
- `record=333,q=0`: symbolic MCQ options.
- `record=37,q=1`: answer/explanation conflict handling.
- `record=376-382`: premise-count mismatch resilience.

## 5. Implementation Principles
- Preserve `docs/Plan.md` as the primary approved direction. Do not implement architecture that contradicts it.
- Use `docs/flow.md` as the runtime architecture contract and `docs/competition.md` as the rule/submission contract.
- Cover the dataset evidence and required cases from `docs/report_past.md`.
- Use `docs/dataset_answer.md` when present, especially for the `choices`-to-`question` flattening clarification.
- Preserve traceability from source documents to batch goals, task IDs, validation, artifacts, and completion criteria.
- Preserve traceability to source records in local evaluation artifacts through stable `sample_id`, `record_id`, and `question_id`.
- Preserve original dataset identifiers and do not rewrite raw record identity.
- Do not modify raw dataset files.
- Do not rely on reference-only fields in runtime inference.
- Do not hardcode answers, record IDs, dataset-specific shortcuts, provider values, model names, URLs, timeouts, concurrency, or retry settings.
- Avoid overfitting to a few hard-case examples; use hard cases as validation slices, not runtime shortcuts.
- Use `.env` as the source of truth for LLM configuration and runtime secrets.
- All future LLM translation, LLM-to-AST, structured output, async batch processing, concurrency, retry, or timeout tasks must use the shared `.env` connection layer from Batch 1.
- For every later LLM-related task, real LLM validation through `.env` is required. Mock tests may supplement live validation but must not replace it.
- Mock tests may supplement but must not replace live LLM tests for LLM-to-AST validation.
- Async LLM behavior must be tested early through Batch 1 sync/async smoke tests and later pipeline-level async validation.
- Validate outputs after each batch before claiming completion.
- Do not skip tests or validation; if a required live validation is blocked, report the blocker explicitly.
- Logs, debug traces, artifacts, and reports must redact API keys, auth headers, and secret-bearing URLs.
- Explanations must be generated from proof traces, not unsupported free-form reasoning.
- Unsupported, ambiguous, low-confidence, or failed reasoning paths must report clear root causes and use the approved fallback/Unknown policy.
- Report unsupported cases explicitly with stage-specific root causes and confidence policy.
- Do not silently ignore malformed records; tag them, emit QC artifacts, and continue only when runtime input remains structurally usable.
- Do not change architecture without approval from the orchestrator/user.
- Do not create unrelated features, UI, tools, or cleanup outside the approved batch scope.
- Do not introduce architecture drift, fake implementations, hidden shortcuts, or passing tests that bypass the approved runtime flow.

## 6. Batch Overview
| Batch id | Batch name | Purpose | Dependencies | Expected output | Validation requirement | Completion criteria |
|---|---|---|---|---|---|---|
| Batch 1 | Environment-Based Live LLM Connection and Async Smoke Test | Establish shared `.env` config, LLM client, validation, retry/timeout, sync smoke, async smoke, and redaction foundation. | Source docs only; must be first. | Config layer, minimal client wrapper, redaction utilities, retry/timeout handling, live sync/async smoke commands. | Config/redaction/client tests plus live sync and async provider smoke through `.env`, or honest credential blocker. | Required env keys validated, no hardcoded provider settings, secrets redacted, live foundation ready for all later LLM work. |
| Batch 2 | Dataset Flattening, Choices Canonicalization, and Runtime-Safe Loader | Convert raw multi-question records into runtime-safe flattened samples and normalize separate `choices`. | Batch 1 only for shared config conventions; source data and docs. | Flattening script/module, runtime-safe loader/sanitizer, QC tags, MCQ extractability diagnostics. | Flattening count/order tests, sanitizer tests, `record=132`-style choices regression, anomaly/QC tests. | Flattened samples preserve IDs, raw data unchanged, runtime path excludes reference fields and raw `choices`. |
| Batch 3 | Candidate Extraction and Question Family Classification | Extract MCQ, Yes/No/Unknown, symbolic, and open-ended candidate envelopes from runtime-safe question text. | Batch 2 normalized question text. | Candidate extractor, question classifier, candidate debug summaries. | MCQ extraction tests, claim extraction tests, open-ended classification tests, symbolic option regression. | Candidates are label-stable, runtime-safe, source-traceable, and extraction failures are stage-attributed. |
| Batch 4 | Parse Frame Schema, AST Schema, and Deterministic Compiler Contracts | Stabilize parse-frame and AST contracts before live parser outputs are trusted. | Batch 3 candidate contracts. | Frame schema, AST schema, deterministic compiler, AST validator, parser/compiler artifact contracts. | Schema tests, compiler fixture tests, AST validation tests, artifact serialization tests. | Frames and ASTs are strict, metadata-preserving, deterministic, and reject ambiguous/lossy structures. |
| Batch 5 | Live LLM Parse-Frame Extractor, Repair Loop, and Cache Modes | Connect shared LLM layer to strict parse-frame extraction, repair, validation, and cache modes. | Batches 1 and 4. | Premise/candidate extractor, prompts, repair loop, local/API cache, frame event artifacts, live parser smoke. | Mock extractor/repair/cache tests plus real `.env` parse-frame smoke. | Live parse frames validate through schema, cache modes work, artifacts are sanitized, no direct LLM final judging. |
| Batch 6 | Async Sample Worker, Failure Isolation, and Debug Trace Artifacts | Orchestrate flattened samples asynchronously with bounded concurrency, deterministic ordering, and debug traces. | Batches 1-5. | Async runner, process-sample pipeline, failure isolation, debug trace writer. | Async concurrency/order tests, failure isolation tests, trace/redaction tests, live async pipeline smoke. | Batch processing continues through per-sample failures and preserves earliest root-cause stage. |
| Batch 7 | AST Normalization, Numeric Feature Detection, and Numeric Evaluator | Normalize ASTs and evaluate numeric/temporal conditions deterministically. | Batches 4 and 6. | Normalizer, numeric detector, numeric evaluator, numeric failure artifacts. | Normalization tests, numeric evaluator tests, artifact tests, `record=34`-style hard-case regression. | Numeric/temporal facts are routed by AST shape, provenance is preserved, invalid numeric cases fail explicitly. |
| Batch 8 | Symbolic Verification Core, Solver Routing, and Answer Decision | Prove supported claims, integrate numeric derived facts, and decide Yes/No/Unknown or MCQ answers. | Batch 7. | Horn prover, contraposition/quantifier helpers, router, decision module, proof trace schema. | Prover tests, routing tests, decision tests, proof trace tests. | Solver output drives answers, Unknown policy is explicit, and proof traces support later explanations. |
| Batch 9 | Numeric Layer Maintainability Checkpoint | Refactor numeric layer after behavior is proven without adding capability or changing answers. | Batch 8 complete. | Focused numeric modules and stronger regression tests. | Full numeric plus solver-decision regression suite and static/dependency checks. | Numeric behavior is unchanged, no LLM calls or reference-field usage added. |
| Batch 10 | Z3 Adapter, Unsupported-Feature Fallback, and Open-Ended Handling | Add approved grounded Z3 support, explicit unsupported fallback, and open-ended proof-grounded policy. | Batches 8 and 9. | Z3 adapter, fallback module, open-ended handler, optional live grounding smoke. | Z3 tests, fallback tests, open-ended grounding tests, live `.env` validation for any LLM verbalization. | Unsupported cases are explicit, Z3 is bounded to approved fragments, open-ended outputs are proof-grounded or Unknown. |
| Batch 11 | Proof-Trace Explanation, Output Formatter, and API Endpoint | Produce competition-shaped API responses with proof-trace-grounded explanations. | Batches 8-10. | Explanation formatter, response formatter, API endpoint, submission adapter. | Explanation grounding tests, output/API contract tests, submission adapter tests, live API smoke. | API accepts only `premises-NL` and `question`; responses include required fields with no leaks. |
| Batch 12 | Evaluation Scripts, Hard-Case Slices, and Final Readiness Reporting | Add reproducible evaluation, slice metrics, root-cause reporting, and final readiness checks. | Batches 1-11. | Evaluation runner, metrics, slice definitions, root-cause reports, live small-slice evaluation command. | Evaluation dry-run tests, metrics tests, slice tests, report tests, live small-slice `.env` run or blocker. | Evaluation is runtime-safe, hard cases are tracked, fingerprints are recorded, final live readiness is documented. |

## 7. Detailed Batches
### Batch 1: Environment-Based Live LLM Connection and Async Smoke Test
#### Goal
Establish the shared `.env`-based LLM configuration, validation, client wrapper, retry/timeout behavior, async smoke path, and secret-safe logging foundation required by all later LLM work.

#### Source Requirements
- `docs/flow.md:12`: all LLM components must use `SHOPAIKEY_MODEL` from `.env`; closed-source APIs are prohibited.
- `docs/flow.md:168`: required LLM config keys include `SHOPAIKEY_BASE_URL`, `SHOPAIKEY_API_KEY`, `SHOPAIKEY_MODEL`, `LLM_TEMPERATURE`, and `LLM_MAX_TOKENS`.
- `docs/flow.md:176`: run live LLM connectivity smoke test as soon as config loading exists.
- `docs/Plan.md:23`: model calls use `.env` configuration and open-source `<=8B` model constraint.

#### Tasks
* [x] B1-T1: Define required runtime `.env` keys and validation rules.
  * expected files: `.env.example`, config module, config tests.
  * expected behavior: missing, empty, invalid, or unsupported values fail with actionable errors and no secret leakage.
  * validation: run config validation tests and a manual missing-key check.
  * source requirement: `docs/flow.md:168`, `docs/Plan.md:23`.
  * notes: include timeout, concurrency, retry, backoff, and generation controls as environment-driven settings; do not hardcode provider, model, base URL, API key, timeout, concurrency, or retry values.
* [x] B1-T2: Implement safe `.env` loading and secret redaction utilities.
  * expected files: config/redaction module and tests.
  * expected behavior: API keys, auth headers, and secret-bearing URLs are never printed or persisted.
  * validation: tests must cover exact secret values, bearer headers, query-token URLs, and nested error payloads.
  * source requirement: `docs/flow.md:161`, `docs/flow.md:182`.
  * notes: logs may show redacted host/model identifiers only when safe.
* [x] B1-T3: Implement a minimal OpenAI-compatible LLM client wrapper using only validated `.env` values.
  * expected files: LLM client module and tests.
  * expected behavior: wrapper sends requests to configured endpoint/model, applies timeout, uses configured generation controls, and returns a normalized response shape.
  * validation: mock client tests plus static check that no provider/model/base URL is hardcoded.
  * source requirement: `docs/flow.md:12`, `docs/flow.md:178`.
  * notes: production/runtime code must not silently switch models.
* [x] B1-T4: Add retry and error handling around the LLM client.
  * expected files: LLM client/retry module and tests.
  * expected behavior: transient failures retry with configured exponential backoff/jitter; authentication/config errors fail fast; timeout errors are stage-attributed.
  * validation: mock tests for transient, permanent, timeout, and malformed response cases.
  * source requirement: `docs/flow.md:186`.
  * notes: retry settings must come from `.env`.
* [x] B1-T5: Add live synchronous smoke test using the real configured provider.
  * expected files: smoke script or test command and documentation in developer-facing docs if present.
  * expected behavior: sends a tiny runtime-safe prompt using only non-reference content, verifies auth/model availability/basic response shape, and redacts secrets.
  * validation: future agents must run the live command with `.env` present and record pass/blocker honestly.
  * source requirement: `docs/flow.md:176`.
  * notes: blocked credentials are acceptable only when reported as blocked, not passed.
* [x] B1-T6: Add live async smoke test.
  * expected files: async smoke script/test.
  * expected behavior: concurrently sends a small number of runtime-safe requests using configured concurrency, timeout, and retry settings; validates result ordering or stable aggregation.
  * validation: run against the real provider through `.env`.
  * source requirement: `docs/flow.md:186`.
  * notes: this is the required foundation for later async batch processing.
* [x] B1-T7: Document exact instructions for future agents to run the live connection tests.
  * expected files: README/dev note if project docs exist, or script help text.
  * expected behavior: future agents can identify required env keys, run sync and async smoke tests, and know how to report credential blockers.
  * validation: command help or documentation review.
  * source requirement: `docs/flow.md:176`, `docs/flow.md:183`.
  * notes: do not include real secrets.

#### Files Expected to Change
- `.env.example`
- configuration module
- LLM client module
- retry/timeout helper module
- smoke test script(s)
- tests for config, redaction, client wrapper, retry, timeout, and live smoke gates
- optional developer documentation for running the live smoke tests

#### Tests / Validation
- Config validation tests.
- Redaction tests.
- Mock LLM client tests for success, missing env, invalid env, timeout, retry, and permanent errors.
- Live sync LLM smoke test through `.env`.
- Live async LLM smoke test through `.env`.

#### Completion Criteria
- Required `.env` keys are defined and validated.
- Safe `.env` loading works without leaking secrets.
- Minimal LLM wrapper uses no hardcoded provider/model/base URL/API key/timeout/concurrency/retry settings.
- Sync and async live provider tests are implemented and run, or credential blockers are reported honestly.
- Future LLM tasks are explicitly instructed to use this shared layer.

#### Handoff Notes for Reviewer
Verify that all LLM paths depend on the shared config/client layer and that live smoke output contains no secrets. Reject completion if only mock tests were run while credentials were available.

### Batch 2: Dataset Flattening, Choices Canonicalization, and Runtime-Safe Loader
#### Goal
Create the local evaluation data path that converts raw multi-question records into runtime-safe one-question samples while preserving local IDs and keeping raw data untouched.

#### Source Requirements
- `docs/flow.md:71`: flatten dataset before local evaluation.
- `docs/flow.md:102`: flattened runtime input fields are `sample_id`, `record_id`, `question_id`, `premises-NL`, and `question`.
- `docs/Plan.md:72`: merge separate `choices` into canonical stable `A./B./C./D.` question lines.
- `docs/dataset_answer.md:7`: do not add `choices` as a runtime input field.
- `docs/report_past.md:84`: `CR-001`; `docs/report_past.md:90`: `CR-002`.

#### Tasks
* [x] B2-T1: Implement raw-to-flattened conversion for one sample per question.
  * expected files: flattening script/module, processed output path, tests.
  * expected behavior: raw records remain unchanged; local IDs are stable and deterministic.
  * validation: sample count matches local evidence and ordering is stable.
  * source requirement: `docs/flow.md:71`, `docs/report_past.md:5`.
  * notes: preserve `record_id` and `question_id` for local orchestration only.
* [x] B2-T2: Canonicalize separate raw `choices` into appended inline `A./B./C./D.` question lines.
  * expected files: flattening module and regression fixture/test.
  * expected behavior: record `132`-style data becomes extractable from `question`; no runtime `choices` field is emitted.
  * validation: regression test for a `record=132,q=0`-style sample.
  * source requirement: `docs/Plan.md:72`, `docs/dataset_answer.md:20`.
  * notes: use stable option order and preserve option text.
* [x] B2-T3: Implement runtime-safe loader and sanitizer.
  * expected files: loader/sanitizer module and tests.
  * expected behavior: runtime inference path receives only `premises-NL` and `question`, with local IDs allowed only for local evaluation orchestration.
  * validation: tests fail if runtime logic reads `premises-FOL`, `answer`, `explanation`, `idx`, or raw `choices`.
  * source requirement: `docs/Plan.md:94`, `docs/flow.md:133`.
  * notes: reference fields remain available only to offline scoring/error analysis code.
* [x] B2-T4: Add dataset anomaly and QC tagging during flattening/loading.
  * expected files: QC module/artifact writer and tests.
  * expected behavior: premise-count mismatches, option extraction risk, answer/explanation conflict signals, and malformed records are tagged without hard-failing structurally usable runtime samples.
  * validation: tests cover records like `376-382` and `37,q=1` through fixtures or slices.
  * source requirement: `docs/report_past.md:33`, `docs/report_past.md:120`.
  * notes: tags must not influence runtime answer generation.
* [x] B2-T5: Add post-flattening MCQ extractability diagnostics.
  * expected files: diagnostic command/artifact and tests.
  * expected behavior: MCQ-labeled answers have extractable options after flattening; missing options produce warning/error artifacts.
  * validation: record `132`-style regression and inline-option samples.
  * source requirement: `docs/Plan.md:99`, `docs/Plan.md:149`.
  * notes: this prevents silent option loss.

#### Files Expected to Change
- dataset flattening script/module
- runtime-safe loader/sanitizer module
- QC/diagnostic module
- tests and small fixtures
- generated `data/processed/...flattened.json` only if the project convention permits generated artifacts

#### Tests / Validation
- Flattening count and order tests.
- Runtime-field sanitizer tests.
- `choices` canonicalization regression for record `132` style.
- QC tagging tests for anomaly/noise cases.
- MCQ option extractability diagnostics.

#### Completion Criteria
- Flattened samples are deterministic and runtime-safe.
- Raw data is not modified.
- Separate `choices` are merged into `question`, not passed as input.
- Reference-only fields cannot be consumed by runtime inference.
- Dataset anomalies are tagged and reported.

#### Handoff Notes for Reviewer
Focus review on runtime input discipline and `choices` handling. Reject completion if `choices` becomes an accepted runtime API field.

### Batch 3: Candidate Extraction and Question Family Classification
#### Goal
Extract candidate claims from normalized questions and classify each sample as MCQ, Yes/No/Unknown, or open-ended without using answer labels at runtime.

#### Source Requirements
- `docs/flow.md:472`: convert questions into candidate claims.
- `docs/flow.md:574`: Yes/No/Unknown and MCQ decision policies.
- `docs/report_past.md:96`: `CR-003`.
- `docs/report_past.md:31`: symbolic/FOL-like question text and options.

#### Tasks
* [x] B3-T1: Implement inline MCQ option extraction from canonical `A./B./C./D.` question text.
  * expected files: candidate extraction module and tests.
  * expected behavior: returns ordered candidate labels and option text without relying on ground-truth answer.
  * validation: tests for standard inline options, multiline options, and symbolic options.
  * source requirement: `docs/flow.md:475`, `docs/report_past.md:22`.
  * notes: input should be the already-normalized question from Batch 2.
* [x] B3-T2: Implement Yes/No/Unknown claim extraction path.
  * expected files: candidate extraction module and tests.
  * expected behavior: returns one candidate claim for verification and supports later checking of claim and explicit negation.
  * validation: tests for yes/no question wording and insufficient-evidence samples.
  * source requirement: `docs/flow.md:483`, `docs/flow.md:574`.
  * notes: do not decide the answer in this batch.
* [x] B3-T3: Implement open-ended classification and best-effort candidate envelope.
  * expected files: question classification module and tests.
  * expected behavior: identifies open-ended questions and records that later stages must synthesize only from proof-trace facts or return Unknown.
  * validation: classification tests using representative prompts.
  * source requirement: `docs/flow.md:489`.
  * notes: open-ended answer generation remains later-batch work.
* [x] B3-T4: Add symbolic-token-aware candidate preservation.
  * expected files: extraction tests and tokenizer/normalization helper if needed.
  * expected behavior: FOL-like option text containing symbols or ASCII equivalents remains intact for later parsing.
  * validation: regression for `record=333,q=0` style symbolic options.
  * source requirement: `docs/report_past.md:52`, `docs/report_past.md:114`.
  * notes: do not rewrite symbols into unsupported semantics.
* [x] B3-T5: Emit candidate extraction debug summaries.
  * expected files: debug trace schema/helper and tests.
  * expected behavior: records question family, candidate count, labels, warnings, and extraction errors in sanitized form.
  * validation: debug trace unit tests.
  * source requirement: `docs/flow.md:629`.
  * notes: no reference-only fields or secrets.

#### Files Expected to Change
- candidate extraction module
- question classification module
- debug summary helper/schema
- tests and fixtures

#### Tests / Validation
- MCQ extraction tests.
- Yes/No/Unknown claim extraction tests.
- Open-ended classification tests.
- Symbolic option preservation regression.
- Candidate extraction error/debug tests.

#### Completion Criteria
- Candidate extraction works from runtime-safe `question` text only.
- MCQ candidates are ordered and label-stable.
- Symbolic options are preserved.
- Extraction failures are stage-attributed.

#### Handoff Notes for Reviewer
Check that answer labels are not used to classify runtime questions. Confirm record `132` style is handled by Batch 2 normalization plus Batch 3 extraction.

### Batch 4: Parse Frame Schema, AST Schema, and Deterministic Compiler Contracts
#### Goal
Define strict parse-frame and typed AST contracts, plus deterministic frame-to-AST compilation for validated non-LLM fixtures.

#### Source Requirements
- `docs/flow.md:234`: LLM emits compact parse frames before AST.
- `docs/flow.md:250`: frame kinds and required metadata.
- `docs/flow.md:435`: deterministic compiler responsibilities.
- `docs/flow.md:503`: AST validation and normalization checks.

#### Tasks
* [x] B4-T1: Define parse-frame schema with discriminated kinds and required metadata.
  * expected files: schema definitions and schema tests.
  * expected behavior: supports `rule`, `fact`, `claim`, `compound`, and `ambiguous`; enforces `source_id`, `source_text`, and premise/candidate metadata where appropriate.
  * validation: valid/invalid schema fixtures.
  * source requirement: `docs/flow.md:250`.
  * notes: ambiguous frames must not compile into facts/rules/claims.
* [x] B4-T2: Define typed AST schema.
  * expected files: AST type/schema module and tests.
  * expected behavior: supports `pred`, `not`, `and`, `or`, `implies`, `forall`, `exists`, `compare`, `arith`, `num_ref`, and numeric literals.
  * validation: schema tests for required fields and invalid nodes.
  * source requirement: `docs/flow.md:463`.
  * notes: root source metadata is mandatory.
* [x] B4-T3: Implement deterministic frame-to-AST compiler for validated frames.
  * expected files: compiler module and tests.
  * expected behavior: converts rules, facts, claims, numeric slots, and compounds structurally without guessing from source text.
  * validation: fixture-based compiler tests.
  * source requirement: `docs/flow.md:435`.
  * notes: compiler must preserve implication direction and explicit negation.
* [x] B4-T4: Add AST validation checks.
  * expected files: AST validator and tests.
  * expected behavior: rejects missing metadata, unbound variables, unstable arity, invalid numeric operands, and malformed nested implications.
  * validation: validator tests for positive and negative cases.
  * source requirement: `docs/flow.md:503`.
  * notes: repair loop is not implemented in this batch.
* [x] B4-T5: Add parser/compiler event artifact contracts.
  * expected files: artifact schema/helper and tests.
  * expected behavior: supports `normalized_frame`, `validated_frame`, `compiled_ast`, and `rejected` events before live extractor exists.
  * validation: artifact serialization tests.
  * source requirement: `docs/flow.md:660`.
  * notes: raw LLM responses are required only once Batch 5 live extractor is active.

#### Files Expected to Change
- parse-frame schema module
- AST schema module
- deterministic compiler module
- AST validator module
- parser/compiler artifact helper
- tests and fixtures

#### Tests / Validation
- Frame schema tests.
- AST schema tests.
- Compiler fixture tests.
- AST validation tests.
- Artifact serialization tests.

#### Completion Criteria
- Frame and AST contracts are explicit and tested.
- Compiler is deterministic and structural-only.
- Ambiguous/lossy frames are rejected.
- Metadata, polarity, direction, and numeric nodes are preserved.

#### Handoff Notes for Reviewer
Reject completion if the compiler uses source text to infer missing semantics or silently compiles ambiguous frames.

### Batch 5: Live LLM Parse-Frame Extractor, Repair Loop, and Cache Modes
#### Goal
Connect the Batch 1 LLM layer to parse-frame extraction, strict structured output validation, repair handling, and premise cache modes.

#### Source Requirements
- `docs/flow.md:176`: second live smoke test for strict compact parse-frame JSON once extractor is implemented.
- `docs/flow.md:186`: local/API cache modes and single-flight locks.
- `docs/flow.md:234`: natural language -> LLM compact parse frame -> validator -> compiler.
- `docs/Plan.md:107`: LLM generates compact parse frames under strict schema.

#### Tasks
* [ ] B5-T1: Implement premise parse-frame extractor using the shared Batch 1 LLM client.
  * expected files: extractor module, prompts/templates, tests.
  * expected behavior: sends runtime-safe premise text and receives compact frame JSON.
  * validation: mock tests and live parse-frame smoke through `.env`.
  * source requirement: `docs/flow.md:234`, `docs/flow.md:176`.
  * notes: no direct final AST generation by the LLM.
* [ ] B5-T2: Implement candidate parse-frame extraction using the same LLM layer.
  * expected files: extractor module and tests.
  * expected behavior: extracts frames for MCQ options, Yes/No claims, symbolic-token candidates, and open-ended envelopes.
  * validation: live `.env` validation on a tiny runtime-safe candidate set plus fixtures.
  * source requirement: `docs/flow.md:472`.
  * notes: real LLM validation is mandatory.
* [ ] B5-T3: Implement structured-output validation and repair loop.
  * expected files: repair/validation module and tests.
  * expected behavior: invalid JSON/schema responses are repaired only through configured retry/repair limits; unrepaired responses get stage-specific errors.
  * validation: tests for malformed JSON, schema mismatch, ambiguous output, timeout, and repair exhaustion.
  * source requirement: `docs/flow.md:520`, `docs/flow.md:653`.
  * notes: repair settings come from `.env` or config.
* [ ] B5-T4: Implement local and API premise cache modes with single-flight locking.
  * expected files: cache module and concurrency tests.
  * expected behavior: local eval key is `record:<record_id>`; API key is `premises_hash:<normalized premises-NL + model/prompt/compiler version>`; concurrent identical premise requests trigger one extraction.
  * validation: concurrency tests.
  * source requirement: `docs/flow.md:198`.
  * notes: include prompt/compiler version in cache fingerprint.
* [ ] B5-T5: Write parser lifecycle artifacts including raw LLM response after extractor activation.
  * expected files: `artifacts/frame_events.jsonl` writer and tests.
  * expected behavior: writes sanitized raw response, normalized frame, validated frame, compiled AST, and rejected events as applicable.
  * validation: artifact tests and secret-redaction checks.
  * source requirement: `docs/flow.md:657`.
  * notes: secrets must never appear in artifacts.
* [ ] B5-T6: Add live parser smoke/quality gate through `.env`.
  * expected files: live smoke command/test.
  * expected behavior: configured model returns strict compact frame JSON for a tiny runtime-safe prompt and frame validation passes.
  * validation: run real provider test or report credential/provider blocker.
  * source requirement: `docs/flow.md:184`, `docs/flow.md:697`.
  * notes: mocks may supplement but must not replace this validation.

#### Files Expected to Change
- parse-frame extractor module
- prompt/template files
- repair loop module
- premise cache module
- frame event artifact writer
- live parser smoke script/test
- tests and fixtures

#### Tests / Validation
- Mock extractor tests.
- Repair loop tests.
- Cache single-flight concurrency tests.
- Secret-safe artifact tests.
- Live parse-frame smoke test through `.env`.

#### Completion Criteria
- Extractor uses the shared `.env` LLM layer.
- Live parse-frame JSON validation is run or honestly blocked.
- Cache modes match local/API requirements.
- Parser artifacts are sanitized and stage-attributed.

#### Handoff Notes for Reviewer
Confirm no LLM parser bypass exists and no final answer is taken from raw LLM output.

### Batch 6: Async Sample Worker, Failure Isolation, and Debug Trace Artifacts
#### Goal
Implement local async evaluation orchestration over flattened samples with bounded concurrency, deterministic ordering, failure isolation, and structured debug traces.

#### Source Requirements
- `docs/flow.md:186`: async execution, retry, timeout, and output ordering.
- `docs/flow.md:211`: example `evaluate_dataset` and `process_sample` structure.
- `docs/flow.md:615`: debug trace and root-cause requirements.
- `docs/Plan.md:74`: async sample worker with bounded concurrency, retry, timeout, and deterministic output ordering.

#### Tasks
* [ ] B6-T1: Implement async dataset evaluation worker over flattened runtime-safe samples.
  * expected files: evaluation runner/orchestrator and tests.
  * expected behavior: processes samples with bounded configured concurrency and preserves output order by `record_id`, then `question_id`.
  * validation: async ordering and concurrency tests.
  * source requirement: `docs/flow.md:186`.
  * notes: use Batch 1 settings for concurrency/timeouts.
* [ ] B6-T2: Integrate premise cache, candidate extraction, parser extraction, compiler validation, and placeholder solver handoff.
  * expected files: process-sample pipeline module and tests.
  * expected behavior: each sample moves through stages and records stage outputs/errors without requiring final solver completeness.
  * validation: pipeline tests with mocked solver handoff.
  * source requirement: `docs/flow.md:211`.
  * notes: do not implement new solver capability in this batch.
* [ ] B6-T3: Implement per-sample failure isolation.
  * expected files: runner and error handling tests.
  * expected behavior: one failed sample produces a failed/partial result with root cause while the batch continues.
  * validation: tests with injected parser timeout and schema failure.
  * source requirement: `docs/flow.md:190`, `docs/flow.md:650`.
  * notes: earliest failure stage must be preserved.
* [ ] B6-T4: Implement structured debug trace collection.
  * expected files: debug trace schema/writer and tests.
  * expected behavior: captures IDs, input summary, cache, candidates, LLM attempts, validation, AST status, solver placeholder, decision placeholder, root cause, and final status.
  * validation: trace schema tests and redaction tests.
  * source requirement: `docs/flow.md:615`.
  * notes: no secrets or reference-only fields.
* [ ] B6-T5: Add real LLM async pipeline smoke with a tiny slice.
  * expected files: gated live smoke command/test.
  * expected behavior: runs the async sample path through the real `.env` LLM for a minimal runtime-safe sample and records parser/cache/debug behavior.
  * validation: live `.env` run or honest blocker report.
  * source requirement: `docs/flow.md:176`, `docs/flow.md:186`.
  * notes: required because this batch uses async LLM processing.

#### Files Expected to Change
- async evaluation runner
- process-sample pipeline module
- debug trace schema/writer
- tests and smoke command

#### Tests / Validation
- Async concurrency tests.
- Deterministic ordering tests.
- Failure isolation tests.
- Debug trace schema/redaction tests.
- Live async pipeline smoke through `.env`.

#### Completion Criteria
- Async evaluation can process flattened samples without stopping on one failure.
- Ordering is deterministic.
- Debug traces are structured, sanitized, and stage-attributed.
- Real LLM async validation is run or explicitly blocked.

#### Handoff Notes for Reviewer
Review root-cause attribution carefully. Parser/frame/compiler errors must not be relabeled later as solver gaps.

### Batch 7: AST Normalization, Numeric Feature Detection, and Numeric Evaluator
#### Goal
Normalize valid ASTs, detect numeric/temporal requirements, and compute deterministic numeric facts for solver handoff.

#### Source Requirements
- `docs/flow.md:354`: numeric frame extraction rules and numeric signals.
- `docs/flow.md:503`: AST validation and normalization.
- `docs/flow.md:529`: numeric computations feed solver context.
- `docs/report_past.md:102`: `CR-004`.

#### Tasks
* [ ] B7-T1: Implement AST normalization.
  * expected files: normalization module and tests.
  * expected behavior: snake_case names, flattened associative `and/or`, removed double negation, preserved implication direction, preserved classical negation, and preserved metadata.
  * validation: normalization tests.
  * source requirement: `docs/flow.md:513`.
  * notes: canonicalization is lexical-only; no broad semantic alias maps.
* [ ] B7-T2: Implement numeric feature detection from frames and ASTs.
  * expected files: numeric detection module and tests.
  * expected behavior: routes numeric slots, compare/arith/num_ref/number nodes, and reliable source-text numeric evidence to numeric evaluator.
  * validation: tests for GPA, percentages, credits, durations, deadlines, and thresholds.
  * source requirement: `docs/flow.md:415`.
  * notes: no record-ID or answer-label routing.
* [ ] B7-T3: Implement deterministic numeric evaluator.
  * expected files: numeric evaluator module and tests.
  * expected behavior: computes arithmetic expressions, comparisons, and temporal/order constraints with provenance.
  * validation: unit tests for thresholds, percentage-of expressions, before/after/within windows, tolerance policy, divide-by-zero, NaN/Inf, invalid ranges, and unit mismatch.
  * source requirement: `docs/flow.md:390`, `docs/flow.md:403`.
  * notes: source text may supplement extraction but must not semantically repair missing frame meaning.
* [ ] B7-T4: Add numeric validation failure artifacts.
  * expected files: artifact writer and tests.
  * expected behavior: strict numeric gate failures are logged with sanitized source references and root-cause category.
  * validation: artifact serialization and redaction tests.
  * source requirement: `docs/flow.md:659`.
  * notes: include provenance and failure stage.
* [ ] B7-T5: Add hard-case regression for `record=34,q=0` style numeric/temporal chain.
  * expected files: tests/fixtures.
  * expected behavior: numeric and temporal signals route through evaluator and produce derived facts or explicit numeric failure reasons.
  * validation: focused regression.
  * source requirement: `docs/report_past.md:36`, `docs/Plan.md:63`.
  * notes: do not hardcode record-specific answer.

#### Files Expected to Change
- AST normalization module
- numeric feature detector
- numeric evaluator
- numeric validation artifact writer
- tests and fixtures

#### Tests / Validation
- Normalization tests.
- Numeric detection tests.
- Numeric evaluator unit tests.
- Numeric artifact tests.
- `record=34`-style hard-case regression.

#### Completion Criteria
- AST normalization preserves source semantics and metadata.
- Numeric/temporal cases are routed deterministically.
- Numeric computations produce provenance for proof traces.
- Invalid numeric cases fail with clear root causes.

#### Handoff Notes for Reviewer
Reject completion if numeric thresholds are converted to generic predicates or if evaluator behavior depends on dataset record IDs.

### Batch 8: Symbolic Verification Core, Solver Routing, and Answer Decision
#### Goal
Implement the core symbolic verifier, route supported fragments, combine numeric derived facts, and decide Yes/No/Unknown or MCQ answers from proof results.

#### Source Requirements
- `docs/flow.md:529`: symbolic verification routes.
- `docs/flow.md:574`: answer decision policy.
- `docs/Plan.md:107`: entailment/contradiction, quantifier support, numeric routing, and fallback strategy.
- `docs/report_past.md:108`: `CR-005`; `docs/report_past.md:126`: `CR-008`.

#### Tasks
* [ ] B8-T1: Implement Horn-compatible facts/rules prover.
  * expected files: solver/prover module and tests.
  * expected behavior: proves supported fact/rule chains and returns used premises, derived facts, and proof steps.
  * validation: unit tests for direct entailment and multi-hop chains.
  * source requirement: `docs/flow.md:532`.
  * notes: no unsupported semantic fallback inside the prover.
* [ ] B8-T2: Implement safe literal-to-literal contraposition rule.
  * expected files: prover module and tests.
  * expected behavior: uses explicit classical negation only for safe literal-to-literal cases.
  * validation: tests for allowed and disallowed contraposition.
  * source requirement: `docs/flow.md:557`.
  * notes: missing evidence is not negation.
* [ ] B8-T3: Implement bounded quantifier handling for supported cases.
  * expected files: quantifier module and tests.
  * expected behavior: schema-level universal matching and bounded instantiation over discovered constants; unsupported unbounded/alternating cases return `solver_capability_gap`.
  * validation: quantifier tests.
  * source requirement: `docs/flow.md:561`.
  * notes: preserve source metadata in instantiations.
* [ ] B8-T4: Implement solver routing across symbolic and numeric contexts.
  * expected files: routing module and tests.
  * expected behavior: selects Horn, contraposition, numeric evaluator result integration, or capability-gap result by AST shape.
  * validation: routing tests with mixed numeric/symbolic fixtures.
  * source requirement: `docs/flow.md:529`.
  * notes: Z3 route is reserved for Batch 10 unless already required by a grounded numeric fragment.
* [ ] B8-T5: Implement Yes/No/Unknown answer decision.
  * expected files: decision module and tests.
  * expected behavior: claim proven -> Yes; negated claim proven -> No; neither -> Unknown.
  * validation: decision tests.
  * source requirement: `docs/flow.md:574`.
  * notes: `Uncertain` is only a scoring/submission alias.
* [ ] B8-T6: Implement MCQ answer decision.
  * expected files: decision module and tests.
  * expected behavior: verifies each option independently, chooses exactly one valid proof, returns Unknown locally for no proof or unresolved ties, and records proof scores/confidence.
  * validation: MCQ tests.
  * source requirement: `docs/flow.md:582`.
  * notes: forced-choice adapter is later/submission-only.
* [ ] B8-T7: Add proof trace and solver debug output.
  * expected files: proof trace schema/writer and tests.
  * expected behavior: includes route used, claim/negated result, used premises, derived facts, numeric computations, unsupported features, and confidence contribution.
  * validation: proof trace tests.
  * source requirement: `docs/flow.md:548`.
  * notes: explanation text is Batch 11.

#### Files Expected to Change
- Horn prover module
- contraposition/quantifier helper modules
- solver router
- answer decision module
- proof trace schema/helper
- tests and fixtures

#### Tests / Validation
- Horn prover tests.
- Contraposition tests.
- Bounded quantifier tests.
- Solver routing tests.
- Yes/No/Unknown and MCQ decision tests.
- Proof trace tests.

#### Completion Criteria
- Supported symbolic fragments produce proof traces.
- Numeric derived facts can participate in solver context.
- Answer decisions follow approved policies.
- Unknown/insufficient-evidence behavior is explicit and tested.

#### Handoff Notes for Reviewer
Verify that solver output, not LLM text, drives final answer decisions.

### Batch 9: Numeric Layer Maintainability Checkpoint
#### Goal
Refactor the numeric layer into focused modules after solver handoff and answer-decision contracts are proven, without changing behavior.

#### Source Requirements
- `docs/flow.md:670`: maintainability checkpoints.
- `docs/flow.md:674`: numeric-layer checkpoint must split Batch 7 numeric layer after Batch 8 proves solver handoff and answer decision; it must not add capabilities, change behavior, call the LLM, use reference-only fields, or introduce dataset-specific logic.

#### Tasks
* [ ] B9-T1: Split numeric detection, expression evaluation, temporal comparison, validation, and artifact writing into focused modules if Batch 7 implementation is too large.
  * expected files: numeric package modules and tests.
  * expected behavior: public behavior and imports remain stable or are migrated with compatibility tests.
  * validation: full numeric and solver-decision regression suite.
  * source requirement: `docs/flow.md:674`.
  * notes: no new solver capabilities.
* [ ] B9-T2: Strengthen regression coverage around existing numeric behavior.
  * expected files: numeric regression tests.
  * expected behavior: pre-refactor and post-refactor outputs match for representative threshold, percentage, temporal, invalid-unit, and failure cases.
  * validation: golden or snapshot-equivalent tests.
  * source requirement: `docs/flow.md:670`.
  * notes: do not use live LLM in this checkpoint.
* [ ] B9-T3: Verify no reference-only fields, dataset-specific logic, or LLM calls were introduced.
  * expected files: tests/static checks if available.
  * expected behavior: numeric layer depends only on parsed frames/ASTs and runtime-safe metadata.
  * validation: dependency/static checks and targeted tests.
  * source requirement: `docs/flow.md:674`.
  * notes: this is a behavior-preserving maintainability batch.

#### Files Expected to Change
- numeric modules from Batch 7
- numeric tests
- import paths if needed

#### Tests / Validation
- Full numeric test suite.
- Solver routing and answer decision regression tests.
- Static/dependency checks for no LLM calls and no reference-field usage.

#### Completion Criteria
- Numeric layer is maintainable and behavior-preserving.
- No answer behavior changes.
- No new capabilities or dataset-specific shortcuts are added.

#### Handoff Notes for Reviewer
Review diffs for accidental behavior changes. This batch should be mostly refactor plus stronger tests.

### Batch 10: Z3 Adapter, Unsupported-Feature Fallback, and Open-Ended Handling
#### Goal
Add grounded Z3 support where approved, explicit unsupported-feature fallback, and best-effort open-ended response policy.

#### Source Requirements
- `docs/flow.md:529`: Z3 for numeric constraints and grounded non-Horn fragments.
- `docs/flow.md:489`: open-ended questions are best-effort in the first milestone.
- `docs/Plan.md:116`: use Z3 for grounded numeric/non-Horn fragments when routed by AST shape.
- `docs/Plan.md:154`: open-ended responses must be grounded in proof-trace facts or return Unknown.

#### Tasks
* [ ] B10-T1: Implement Z3 adapter for grounded numeric constraints and finite Boolean non-Horn fragments.
  * expected files: Z3 adapter module and tests.
  * expected behavior: translates supported grounded ASTs to Z3, returns proof/unsat/status metadata, and rejects unsupported ungrounded cases.
  * validation: adapter tests.
  * source requirement: `docs/flow.md:536`.
  * notes: use Z3 only by routed AST shape, not dataset patterns.
* [ ] B10-T2: Implement unsupported-feature fallback and confidence capping.
  * expected files: fallback module and tests.
  * expected behavior: unsupported, ambiguous, or low-confidence cases return internal Unknown or semantic fallback with capped confidence and clear root cause.
  * validation: fallback tests.
  * source requirement: `docs/flow.md:543`, `docs/Plan.md:120`.
  * notes: fallback must not invent proof.
* [ ] B10-T3: Implement open-ended best-effort synthesis from proof-trace facts only.
  * expected files: open-ended handler and tests.
  * expected behavior: returns grounded synthesized response when proof facts support it; otherwise Unknown with low confidence and explicit fallback reason.
  * validation: open-ended tests.
  * source requirement: `docs/flow.md:489`, `docs/Plan.md:154`.
  * notes: LLM verbalization may be used only through Batch 1 shared layer and must be live-validated if added.
* [ ] B10-T4: Add real LLM validation for any LLM-assisted open-ended or fallback verbalization.
  * expected files: live test/smoke if LLM verbalization is implemented.
  * expected behavior: uses `.env` provider, redacts secrets, and verifies output stays grounded in supplied proof trace.
  * validation: live `.env` run or honest blocker.
  * source requirement: `docs/flow.md:176`, `docs/flow.md:605`.
  * notes: if no LLM verbalization is implemented, document that none is required for this batch.

#### Files Expected to Change
- Z3 adapter module
- solver fallback module
- open-ended handler
- tests and fixtures
- optional live LLM grounding smoke if verbalization is LLM-assisted

#### Tests / Validation
- Z3 adapter tests.
- Unsupported-feature and confidence fallback tests.
- Open-ended grounding tests.
- Live `.env` validation for any LLM-assisted verbalization.

#### Completion Criteria
- Z3 support is limited to approved grounded cases.
- Unsupported cases are explicit and traceable.
- Open-ended answers are proof-grounded or Unknown.
- Any LLM-assisted text generation uses the shared live-validated `.env` layer.

#### Handoff Notes for Reviewer
Reject completion if Z3 is used as a broad semantic guesser or open-ended answers include facts absent from proof traces.

### Batch 11: Proof-Trace Explanation, Output Formatter, and API Endpoint
#### Goal
Format final responses with answer, proof-trace-grounded explanation, optional evidence fields, confidence, and an API endpoint matching competition input constraints.

#### Source Requirements
- `docs/flow.md:133`: API accepts `premises-NL` and `question`.
- `docs/flow.md:605`: explanations come from proof trace, not free-form LLM reasoning.
- `docs/competition.md:158`: API endpoint and response fields are submission requirements.
- `docs/Plan.md:123`: required API response fields include `answer`, `explanation`, `fol`, `cot`, `premises`, and `confidence`.

#### Tasks
* [ ] B11-T1: Implement proof-trace-to-explanation formatter.
  * expected files: explanation module and tests.
  * expected behavior: cites premise numbers, describes reasoning chain, includes computed numeric values and provenance when relevant, and avoids unsupported claims.
  * validation: explanation grounding tests.
  * source requirement: `docs/flow.md:605`.
  * notes: if LLM verbalization is used, it must use Batch 1 layer and live `.env` validation.
* [ ] B11-T2: Implement final output formatter.
  * expected files: response formatter and tests.
  * expected behavior: always returns required fields with answer, explanation, fol, cot, premises, and confidence where configured; optional evidence is schema-stable.
  * validation: output contract tests.
  * source requirement: `docs/Plan.md:123`, `docs/competition.md:158`.
  * notes: do not expose internal secrets or reference-only fields.
* [ ] B11-T3: Implement API endpoint accepting only `premises-NL` and `question`.
  * expected files: API app/router and tests.
  * expected behavior: validates request shape, rejects or ignores unsupported runtime fields according to explicit policy, runs the runtime pipeline, and returns formatted response.
  * validation: API contract tests.
  * source requirement: `docs/flow.md:133`, `docs/competition.md:136`.
  * notes: local IDs are not required for submitted API requests.
* [ ] B11-T4: Implement submission adapter for label aliases and optional forced MCQ policy if required.
  * expected files: submission adapter and tests.
  * expected behavior: maps `Unknown`/`Uncertain` only at scoring/submission boundary and records any forced-choice fallback trace with confidence penalty.
  * validation: adapter tests.
  * source requirement: `docs/flow.md:590`, `docs/report_past.md:76`.
  * notes: keep internal canonical answer as Unknown.
* [ ] B11-T5: Add live API smoke with `.env` LLM path.
  * expected files: integration smoke test/command.
  * expected behavior: sends a tiny runtime-safe request through API/pipeline and receives a valid response with redacted logs.
  * validation: live `.env` run or honest blocker.
  * source requirement: `docs/flow.md:176`, `docs/competition.md:158`.
  * notes: mocks are not enough for LLM-backed API readiness.

#### Files Expected to Change
- explanation formatter
- response formatter/schema
- API app/router
- submission adapter
- API and integration tests

#### Tests / Validation
- Explanation grounding tests.
- Output schema tests.
- API request/response contract tests.
- Submission adapter tests.
- Live API smoke through `.env`.

#### Completion Criteria
- API input matches competition/runtime constraints.
- Responses include required fields.
- Explanations are proof-trace-grounded.
- Live API path is validated or credential blocker is reported.

#### Handoff Notes for Reviewer
Check for reference-field leakage in responses and logs. Confirm explanation content is derived from proof traces.

### Batch 12: Evaluation Scripts, Hard-Case Slices, and Final Readiness Reporting
#### Goal
Add reproducible local evaluation, slice metrics, hard-case validations, root-cause reports, and final readiness checks.

#### Source Requirements
- `docs/Plan.md:156`: evaluation metrics and slice-based evaluation.
- `docs/Plan.md:163`: hard-case and special slice tracking.
- `docs/report_past.md:35`: required hard/edge cases.
- `docs/competition.md:126`: scoring dimensions are correctness, explanation quality, and reasoning depth.

#### Tasks
* [ ] B12-T1: Implement local evaluation script over flattened samples.
  * expected files: evaluation script/module and tests.
  * expected behavior: runs predictions, compares offline labels only in scoring layer, and records dataset/model/config fingerprints.
  * validation: dry-run and fixture evaluation tests.
  * source requirement: `docs/Plan.md:156`.
  * notes: runtime inference must still receive only runtime-safe fields.
* [ ] B12-T2: Implement metrics by answer family and explanation/evidence checks.
  * expected files: metrics module and tests.
  * expected behavior: reports correctness by Yes/No/Unknown, MCQ, and open-ended family; tracks explanation grounding and reasoning-depth evidence proxies.
  * validation: metrics tests.
  * source requirement: `docs/competition.md:126`, `docs/Plan.md:158`.
  * notes: separate automatic correctness from explanation quality signals.
* [ ] B12-T3: Implement required hard-case slice evaluation.
  * expected files: slice definitions, tests, and report writer.
  * expected behavior: tracks numeric/temporal, symbolic-token, anomaly/noise, option-format, and open-ended slices including records `34`, `132`, `333`, `37`, and `376-382`.
  * validation: slice selection tests.
  * source requirement: `docs/Plan.md:63`, `docs/Plan.md:163`.
  * notes: do not hardcode answers in runtime logic.
* [ ] B12-T4: Implement root-cause category reporting.
  * expected files: report writer and tests.
  * expected behavior: aggregates earliest failure stages, parser failures, numeric failures, annotation noise, MCQ option-missing cases, fallback usage, timeout, and API errors.
  * validation: report tests with synthetic traces.
  * source requirement: `docs/flow.md:650`, `docs/Plan.md:166`.
  * notes: separate model errors from annotation-noise-flagged cases.
* [ ] B12-T5: Add final live evaluation smoke on a small runtime-safe slice.
  * expected files: gated live evaluation command.
  * expected behavior: uses real `.env` LLM through the full pipeline on a small slice and produces predictions/debug/evaluation artifacts with secrets redacted.
  * validation: live run or honest blocker report.
  * source requirement: `docs/flow.md:176`, `docs/Plan.md:150`.
  * notes: mock-only final readiness is not acceptable when credentials are available.

#### Files Expected to Change
- evaluation script/module
- metrics module
- slice definitions/report writer
- root-cause reporting module
- tests and fixtures
- generated evaluation artifacts under an artifacts/output directory if project convention permits

#### Tests / Validation
- Evaluation dry-run tests.
- Metrics tests.
- Slice selection tests.
- Root-cause report tests.
- Live small-slice evaluation through `.env`.

#### Completion Criteria
- Evaluation is reproducible and runtime-safe.
- Required dataset slices are tracked separately.
- Reports include dataset/model/config fingerprints.
- Final live smoke is run or blocked honestly.

#### Handoff Notes for Reviewer
Confirm scoring code may read labels but runtime prediction code cannot. Check that hard-case reporting is slice-based, not runtime hardcoding.

## 8. Cross-Batch Dependencies
- Batch 1 is mandatory first. All LLM, async timeout, retry, concurrency, and live validation work depends on its shared `.env` connection layer.
- Batch 2 produces flattened runtime-safe samples needed by Batches 3, 6, and 12.
- Batch 3 candidate extraction depends on Batch 2 question normalization.
- Batch 4 schemas and compiler contracts are required before Batch 5 live parse-frame extraction can safely compile/validate model outputs.
- Batch 5 depends on Batches 1 and 4.
- Batch 6 depends on Batches 1, 2, 3, 4, and 5.
- Batch 7 depends on AST outputs from Batch 4 and pipeline/debug conventions from Batch 6.
- Batch 8 depends on normalized ASTs and numeric derived facts from Batch 7.
- Batch 9 depends on Batch 8 proving solver handoff and answer-decision behavior.
- Batch 10 depends on Batch 8 solver routing and Batch 9 numeric stability.
- Batch 11 depends on proof traces and decisions from Batches 8-10.
- Batch 12 depends on the full runtime pipeline from Batches 1-11.

## 9. Validation and Evaluation Tasks
- Every batch must include tests or validation matching its completion criteria.
- Every LLM-related batch must run real `.env` validation or report credential/provider blockage honestly.
- Mock tests may cover edge cases but must not be the only validation for live LLM functionality.
- Runtime contract tests must prove inference uses only `premises-NL` and `question`.
- Output contract tests must prove required response fields exist.
- Flattening tests must prove separate raw `choices` are canonicalized into `question`.
- Parser/compiler tests must prove strict frame validation, deterministic compilation, metadata preservation, and rejection of lossy/ambiguous frames.
- Async tests must prove bounded concurrency, retry, timeout, single-flight cache behavior, failure isolation, and deterministic ordering.
- Numeric tests must prove threshold/comparison/temporal handling and invalid numeric rejection.
- Solver tests must prove entailment, contradiction, Unknown, MCQ tie/no-proof behavior, and proof-trace generation.
- Evaluation must report correctness, explanation grounding, reasoning-depth evidence, root-cause categories, cache stats, and hard-case slice metrics.

## 10. Known Risks and Guardrails
- Risk: closed-source or wrong-size model use. Guardrail: `.env` model-source validation and live smoke through configured model.
- Risk: secret leakage. Guardrail: redaction tests for logs, traces, artifacts, and error payloads.
- Risk: reference-field leakage. Guardrail: sanitizer and runtime contract tests.
- Risk: candidate loss from `choices` field. Guardrail: flatten-time canonicalization and record `132`-style regression.
- Risk: parser fragility on mixed NL, symbolic, and long-chain clauses. Guardrail: strict schemas, repair loop limits, rejected-frame artifacts, and live parser smoke.
- Risk: numeric/temporal misinterpretation. Guardrail: numeric slots, deterministic evaluator, unit/range validation, and hard-case regression.
- Risk: annotation noise distorts metrics. Guardrail: QC tags and reports separating annotation-noise cases from model failures.
- Risk: overbroad semantic fallback. Guardrail: confidence caps, root-cause trace, and proof-grounded explanation checks.
- Risk: performance instability under async load. Guardrail: bounded concurrency, timeout, retries, single-flight cache, and failure isolation.

## 11. Open Questions and Conflict Handling
- Dataset version conflict remains open: competition text says 464 records / 913 questions, while the local raw snapshot is 411 records / 808 questions. Use local snapshot for local evaluation and record dataset version metadata in artifacts.
- Final scoring policy for unresolved MCQ remains unclear. Keep internal Unknown policy and implement any forced-choice behavior only in a submission adapter.
- Final P1/P2/P3 weights are not published. Report all three dimensions separately.
- If future workshop rules contradict this task plan, future agents must stop and request a plan revision rather than silently changing architecture.
- If credentials are unavailable for live validation, future agents must mark live checks as blocked and explain the blocker; they must not claim pass from mock tests.

## 12. Out-of-Scope Items
- Modifying raw dataset files.
- Modifying `docs/Plan.md`, `docs/flow.md`, `docs/competition.md`, `docs/report_past.md`, `docs/dataset_answer.md`, `review.json`, or `task_review.json` unless a later user instruction explicitly asks for it.
- Using closed-source LLMs such as GPT, Claude, or Gemini.
- Hardcoding dataset answers, record-specific decisions, provider settings, model names, base URLs, secrets, timeout values, concurrency values, or retry values.
- Passing raw `choices` as a runtime API/input field.
- Reading `premises-FOL`, `answer`, `explanation`, or `idx` in runtime prediction code.
- Generating explanations from unsupported free-form LLM reasoning.
- Treating optional evidence fields as permission to leak debug traces, secrets, or reference-only labels.

## 13. Final Execution Readiness Checklist
- [ ] The task plan follows `docs/Plan.md` as the primary approved direction.
- [ ] The task plan respects `docs/flow.md` runtime flow, input constraints, parse-frame/AST architecture, async/cache rules, debug trace rules, and build order.
- [ ] The task plan respects `docs/competition.md` open-source model rule, closed-source model prohibition, evaluation dimensions, test format, and API submission expectations.
- [ ] The task plan covers `docs/report_past.md` dataset evidence, coverage requirements, hard cases, anomalies, and risks.
- [ ] The task plan uses `docs/dataset_answer.md` because it is available, especially for the separate `choices` flattening policy.
- [ ] Work is organized as batch-based execution with one batch completed and reviewed at a time.
- [ ] Cross-batch dependencies are clear and preserve the approved architecture order after mandatory Batch 1.
- [ ] Every batch includes validation requirements.
- [ ] Every batch includes completion criteria.
- [ ] Every batch includes reviewer handoff notes.
- [ ] Batch 1 completed first and established shared `.env` LLM connection, validation, sync smoke, and async smoke.
- [ ] Batch 1 includes live synchronous LLM smoke testing through `.env`.
- [ ] Batch 1 includes live async LLM smoke testing through `.env`.
- [ ] All later LLM tasks use the Batch 1 shared client/config layer.
- [ ] All LLM configuration, including model, base URL, API key, timeout, retry, concurrency, and generation controls, comes through `.env` or validated config derived from `.env`.
- [ ] Every LLM-related batch includes real `.env` validation or an honest blocker report.
- [ ] LLM-to-AST work uses real LLM calls for validation through `.env`; mocks only supplement live validation.
- [ ] Runtime inference consumes only `premises-NL` and `question`.
- [ ] Separate raw `choices` are merged into canonical question text during flattening.
- [ ] Raw dataset files remain unmodified.
- [ ] No dataset files are modified by planning or implementation work except generated processed/evaluation artifacts explicitly allowed by a later batch.
- [ ] Reference-only fields are restricted to offline scoring, validation, training analysis, and error reports.
- [ ] Parse frames, ASTs, numeric evaluator, solvers, decisions, explanations, API responses, and evaluation reports are covered by tests.
- [ ] Hard-case slices include records `34`, `132`, `333`, `37`, and `376-382`.
- [ ] Logs, traces, artifacts, and reports redact secrets.
- [ ] No secrets are hardcoded, printed, or logged.
- [ ] Output responses include required fields and proof-trace-grounded explanations.
- [ ] Unsupported, malformed, blocked, and failed paths are reported explicitly with root causes.
- [ ] The task plan is detailed enough for future execution agents to identify files, expected behavior, validation, source requirements, and reviewer handoff expectations.
- [ ] No implementation code is included in this planning document.
- [ ] No architecture drift from the approved plan is introduced.
- [ ] No unrelated features or optional tracks are mixed into the mandatory chain.
- [ ] Completion reports from future agents list completed task IDs, files changed, tests/validations run, live validation status, artifacts produced, risks, and handoff notes.
