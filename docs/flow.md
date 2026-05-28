# EXACT 2026 Reasoning Flow

## Goal

Build an explainable QA system for educational logic questions. At evaluation time, the submitted runtime receives only:

- `premises-NL`
- `question`

Training annotations such as `premises-FOL`, `answers`, `explanation`, and `idx` are used only for offline learning, validation, scoring, and error analysis. They must not be assumed available at runtime.

All LLM components must use the model configured in `.env` through `SHOPAIKEY_MODEL`. The current local model identifier is `qwen2.5-7b-instruct`, which fits the competition rule for open-source models with 8B parameters or fewer. Closed-source APIs such as GPT, Claude, or Gemini must not be used in the submitted system.

## High-Level Flow

```text
Raw dataset
records with multiple questions
  |
  v
Flatten dataset
one sample per question
  |
  v
Runtime-safe sample
premises-NL + question + local IDs only
  |
  v
Async sample worker
bounded concurrency, retry, timeout
  |
  v
Premise parse-frame extraction/cache
LLM emits compact frames once per record_id or premise hash
  |
  v
Frame validation and deterministic frame-to-AST compilation
code builds formal AST; LLM does not produce final AST directly
  |
  v
Candidate extraction
MCQ options or Yes/No/Unknown/open claim
  |
  v
Candidate parse-frame extraction and frame-to-AST compilation
question/options become candidate claim ASTs
  |
  v
AST validation and normalization
schema, variables, predicates, numeric nodes, source metadata
  |
  v
Feature detection and numeric extraction
numeric slots, compare/arith/num_ref, source-text fallback
  |
  v
Symbolic verification
Horn prover / contraposition / bounded quantifiers / Z3 / fallback
  |
  v
Proof trace and debug trace
used premises, derived facts, root-cause stages
  |
  v
Output formatter
answer + explanation + optional evidence
```

## Runtime Pipeline

### 1. Dataset Flattening

Before local evaluation, flatten the raw dataset into one sample per question.

Raw records contain one shared `premises-NL` list and multiple questions:

```json
{
  "premises-NL": ["..."],
  "questions": ["Question 1?", "Question 2?"],
  "answers": ["Yes", "A"],
  "explanation": ["...", "..."]
}
```

The flattened file contains one local evaluation sample per question:

```json
{
  "sample_id": "record_0000_question_0001",
  "record_id": 0,
  "question_id": 1,
  "premises-NL": ["..."],
  "premises-FOL": ["..."],
  "question": "Question 2?",
  "answer": "A",
  "explanation": "...",
  "idx": [7, 10]
}
```

Runtime input fields in the flattened file:

- `sample_id`
- `record_id`
- `question_id`
- `premises-NL`
- `question`

Reference-only fields:

- `premises-FOL`
- `answer`
- `explanation`
- `idx`

Reference-only fields may be used for local training, validation, scoring, and error analysis. They must not be read by the runtime inference path that generates predictions.

Use the flattening script:

```bash
python scripts/flatten_dataset.py \
  --input data/raw/Logic_Based_Educational_Queries.json \
  --output data/processed/Logic_Based_Educational_Queries.flattened.json
```

Local evaluation should read from:

```text
data/processed/Logic_Based_Educational_Queries.flattened.json
```

## 2. Runtime Input and API Shape

The submitted API endpoint should accept:

```json
{
  "premises-NL": ["..."],
  "question": "..."
}
```

The API response must include at least:

```json
{
  "answer": "Yes",
  "explanation": "..."
}
```

Optional evidence fields are encouraged:

```json
{
  "fol": "...",
  "cot": ["Step 1: ..."],
  "premises": ["Premise 2: ..."],
  "confidence": 0.86
}
```

Use `.env` only for runtime configuration and secrets such as model endpoint, internal API key, host, port, timeout, retry settings, and concurrency. Do not print `.env` values or write raw secrets into logs, debug traces, predictions, or scoring artifacts.

Required LLM config:

- `SHOPAIKEY_BASE_URL`: OpenAI-compatible model endpoint.
- `SHOPAIKEY_API_KEY`: model API key; secret, never logged.
- `SHOPAIKEY_MODEL`: model identifier used by all LLM calls; current local value is `qwen2.5-7b-instruct`.
- `LLM_TEMPERATURE`: deterministic low-temperature parsing setting.
- `LLM_MAX_TOKENS`: maximum generation budget for parse-frame JSON.

The implementation should treat `.env` as the source of truth for model selection. Tests may use a mock LLM client, but production/runtime code must not silently switch to another model.

Run a live LLM connectivity smoke test as soon as config loading exists and before adding substantial downstream logic. The smoke test should:

- use `SHOPAIKEY_BASE_URL`, `SHOPAIKEY_API_KEY`, and `SHOPAIKEY_MODEL` from `.env`
- send a tiny runtime-safe prompt that does not include dataset reference fields
- verify authentication, model availability, timeout behavior, and basic response shape
- redact API keys, auth headers, and secret-bearing URLs from logs and traces
- fail or report a blocked live validation clearly instead of silently relying only on mocks

When the LLM parse-frame extractor is implemented, run a second live smoke test that asks the configured model for strict compact parse-frame JSON and validates the returned frame shape.

## 3. Async Execution and Cache Modes

Local evaluation processes flattened samples asynchronously.

Recommended behavior:

- Use bounded concurrency, for example `max_concurrency = 4-16`, depending on API latency and rate limits.
- Retry transient API failures with exponential backoff and jitter.
- Apply per-request and per-sample timeouts.
- Continue the batch when one sample fails.
- Preserve local output order by `record_id`, then `question_id`.

There are two premise cache modes:

```text
Local evaluation:
  key = record:<record_id>
  reason = multiple flattened samples share the same original premises

API runtime:
  key = premises_hash:<hash(normalized premises-NL + model/prompt/compiler version)>
  reason = submitted API requests do not include record_id
```

Both cache modes must use single-flight locks so concurrent requests for the same premise set trigger only one LLM parse-frame extraction.

Example structure:

```text
evaluate_dataset(flattened_samples):
  load .env
  sanitize each sample
  create semaphore(max_concurrency)
  submit process_sample(sample) for each sample
  gather results with failure isolation
  sort by record_id, question_id
  write predictions and debug traces

process_sample(sample):
  get or create premise frame/AST bundle for sample.record_id
  extract candidates from question
  extract candidate parse frames
  compile candidate frames to AST
  validate and normalize ASTs
  run numeric and symbolic verification
  format output
```

## 4. Parse Frames Before AST

The LLM is the semantic parser, not the solver and not the final judge.

It should emit compact parse frames rather than full formal ASTs:

```text
natural language
  -> LLM compact parse frame
  -> frame validator
  -> deterministic frame-to-AST compiler
  -> AST validator and normalizer
```

This keeps prompts smaller, reduces invalid JSON/logic outputs, and lets code own the formal AST structure.

### Compact Parse Frame Kinds

Use a strict JSON schema with `kind` as discriminator.

Frame kinds:

- `rule`
- `fact`
- `claim`
- `compound`
- `ambiguous`

Common slot types:

- `predicate`
- `numeric_condition`
- `numeric_value`
- `arithmetic_expression`
- `entity_relation`

Relation-contract rules:

- `entity_relation` style content must preserve `subject`, `relation`, `object`, and optional `complement` roles.
- Frames that lose object/complement roles must fail validation instead of compiling as lossy predicates.
- Clause-side integrity is mandatory: `if` operands stay antecedent-side, `then` operands stay consequent-side.
- If meaning cannot be preserved, the parser must emit `ambiguous`.

Required metadata:

- `source_id`
- `source_text`
- `premise_id` for premise frames
- `candidate_label` for candidate frames
- `warnings`

Example rule frame:

```json
{
  "kind": "rule",
  "scope": "students",
  "if": [
    {
      "type": "numeric_condition",
      "entity": "student",
      "attribute": "cumulative_gpa",
      "op": ">=",
      "value": 7.0
    }
  ],
  "then": [
    {
      "type": "predicate",
      "entity": "student",
      "name": "allowed_change_major",
      "polarity": true
    }
  ],
  "source_id": "premise_0001",
  "source_text": "Students are allowed to change majors if their cumulative GPA is 7.0 or higher.",
  "premise_id": 1,
  "warnings": []
}
```

Example fact frame:

```json
{
  "kind": "fact",
  "entity": "Mai",
  "facts": [
    {
      "type": "numeric_value",
      "attribute": "cumulative_gpa",
      "value": 7.2
    }
  ],
  "source_id": "premise_0022",
  "source_text": "Mai has a cumulative GPA of 7.2.",
  "premise_id": 22,
  "warnings": []
}
```

Example claim frame:

```json
{
  "kind": "claim",
  "answer_type": "yes_no",
  "claim": {
    "type": "predicate",
    "entity": "Mai",
    "name": "successfully_change_major",
    "polarity": true
  },
  "source_id": "question",
  "source_text": "Can Mai successfully change majors?",
  "candidate_label": "claim",
  "warnings": []
}
```

## 5. Numeric Frame Extraction

The LLM must emit numeric frame slots when source text contains numeric requirements or facts.

Numeric signals include:

- quantities
- percentages
- GPA
- scores
- credits
- semesters
- deadlines
- durations
- fees
- penalties
- averages
- weighted averages
- ranks
- thresholds
- comparison phrases

Comparison phrases include:

- `at least`
- `higher than`
- `lower than`
- `no more than`
- `within`
- `before`
- `after`
- `between`
- `or higher`
- `or lower`
- `minimum`
- `maximum`

Rules:

- Numeric facts about named entities should use `numeric_value`.
- Numeric requirements or thresholds should use `numeric_condition`.
- Computed expressions should use `arithmetic_expression`.
- Do not turn numeric requirements into generic predicates such as `meets_exam_requirement`.
- Do not flatten expressions such as `75% of the standard score` into a bare number unless the deterministic numeric layer computes it.
- Numeric validation must reject unit/dimension mismatch, invalid ranges, divide-by-zero, NaN/Inf, and out-of-policy tolerance cases.
- Numeric path must not semantically repair meaning from source text; source text may supplement extraction only.

Examples:

```text
"Mai scored 78%."
-> numeric_value(attribute="exam_score", entity="Mai", value=78, unit="percent")

"Students must have a GPA of 7.0 or higher."
-> numeric_condition(attribute="gpa", entity="student", op=">=", value=7.0)

"Students must achieve at least 75% of the standard score."
-> numeric_condition(
     attribute="exam_score",
     entity="student",
     op=">=",
     expression=arithmetic_expression(
       op="percentage_of",
       operands=[
         {value: 75, unit: "percent"},
         {attribute: "standard_score"}
       ]
     )
   )
```

Numeric routing should be based primarily on parse frames and compiled AST nodes, not record IDs or answer labels.

```text
numeric frame slot found
or compiled AST has compare / arith / num_ref / number
or reliable source text contains numeric evidence
  -> route through numeric evaluator
  -> add derived numeric facts to solver context and proof trace
```

## 6. Frame-to-AST Compilation

The deterministic compiler converts validated frames into a formal typed logic AST.

Compiler responsibilities:

- Convert `rule` frames into `forall` / `implies` AST structures.
- Convert `fact` frames into ground predicate, numeric value, or comparison ASTs.
- Convert `claim` frames into candidate ASTs.
- Convert numeric slots into `compare`, `arith`, `num_ref`, and number terms.
- Add source metadata to AST roots.
- Preserve implication direction.
- Preserve explicit polarity/negation.
- Record compiler warnings when a frame cannot be safely compiled.
- Compiler is structural-only and must not use source text to guess semantics.
- `ambiguous` frames must not compile into fact/rule/claim ASTs.

AST root metadata is required:

- Premise AST root: `source_id`, `source_text`, `premise_id`.
- Candidate AST root: `source_id`, `source_text`, `candidate_label`.
- API/runtime question AST root: `source_id`, `source_text`.

The AST should support at least:

- `pred`
- `not`
- `and`
- `or`
- `implies`
- `forall`
- `exists`
- `compare`
- `arith`
- `num_ref`
- numeric literals

## 7. Candidate Extraction

Convert the question into one or more candidate claims.

For multiple-choice questions:

```text
A -> candidate claim A
B -> candidate claim B
C -> candidate claim C
D -> candidate claim D
```

Each option is parsed into a candidate frame, compiled into a claim AST, and verified independently.

For Yes/No/Unknown questions:

```text
question -> candidate claim
```

Then verify both the claim and its explicit negation.

Open-ended questions are best-effort in the first milestone:

- classify them as open-ended
- ask the verifier for strongest relevant entailed facts
- synthesize only from proof-trace facts
- return `Unknown` with low confidence if no grounded fact exists
- report open-ended metrics separately from core metrics

## 8. AST Validation and Normalization

Before symbolic reasoning, validate and normalize compiled ASTs.

Checks should include:

- Required fields exist for each node type.
- Root source metadata exists.
- Variables are bound by quantifiers or explicitly treated as constants.
- Predicate names are normalized consistently across premises and options.
- Predicate arity is stable within one premise bundle.
- Numeric expressions have valid operands and units where possible.
- Nested implications preserve scope.

Normalization should:

- Normalize predicate and numeric reference names to snake_case.
- Flatten associative `and` / `or`.
- Remove double negation.
- Preserve implication direction.
- Preserve explicit classical negation.
- Preserve all source metadata needed for proof trace citations.
- Keep canonicalization lexical-only; do not apply static dataset/domain token-map aliases or broad semantic merges.

Invalid frames or ASTs should be repaired only through the configured repair loop. If repair fails, record the stage-specific root cause and route to fallback only when allowed.

## 9. Symbolic Verification

Route ASTs by logic fragment.

```text
Horn-compatible facts/rules
  -> custom Horn prover

literal-to-literal contraposition
  -> Horn prover with explicit contraposition proof rule

numeric deterministic computations
  -> numeric evaluator, then solver context

numeric constraints / propositional non-Horn fragments
  -> Z3 adapter

nested implication / meta-logic
  -> Z3 only when grounded to finite Boolean formulas
  -> otherwise solver_capability_gap

unsupported or low-confidence cases
  -> semantic fallback with capped confidence
```

The verifier should return:

- whether the claim is entailed
- whether the negated claim is entailed
- route used
- used premises
- derived facts
- numeric computations
- proof trace
- unsupported features
- confidence contribution

Contraposition is allowed only for safe literal-to-literal cases using explicit classical negation, not missing evidence.

Quantifier handling should support:

- schema-level universal matching for generic universal premise/candidate formulas
- bounded instantiation over discovered constants
- explicit `solver_capability_gap` for unsupported unbounded or alternating quantifier cases

## 10. Answer Decision

For Yes/No/Unknown:

```text
claim proven          -> Yes
negated claim proven  -> No
neither proven        -> Unknown
```

Use `Unknown` as the internal canonical label. Treat `Uncertain` as an alias at scoring/submission boundaries.

For multiple-choice:

```text
verify each option
if exactly one option has a valid proof, choose that option
if no option has a valid proof, return Unknown locally
if multiple options are provable, choose one only when proof strength clearly selects it
otherwise return Unknown locally
```

If the official evaluator requires only `A/B/C/D`, use a separate submission adapter. Forced-choice traces must include:

- original internal answer
- selected fallback option
- candidate scores
- threshold
- confidence penalty
- reason the adapter was required

## 11. Explanation Generation

Generate explanations from the proof trace, not from free-form LLM reasoning.

The explanation should cite premise numbers and describe the reasoning chain.

LLMs may be used only to verbalize proof traces into clearer natural language. They must not invent unsupported reasoning.

Numeric explanations must cite both premise numbers and computed values.

## 12. Debug Trace and Root-Cause Analysis

Keep a structured debug trace for every local flattened sample and every API request when debug logging is enabled.

The debug trace is separate from the public response and must never include secrets or reference-only fields.

Recommended debug stages:

- IDs: `sample_id`, `record_id`, `question_id`, `premises_hash` when available.
- Input summary: premise count, question type, candidate count.
- Cache: mode, redacted key/hash, cache hit, single-flight wait.
- Candidate extraction: status, candidates, warnings.
- LLM frame extraction: model identifier, prompt version, attempts, retries, timeout, repair count, cache hit.
- Frame validation and compilation: frame kind, validation errors, compiler version, compile warnings, AST validation status.
- AST validation: node counts, errors, warnings.
- Normalization: predicate map, arity warnings, source metadata coverage.
- Quantifier instantiation: constants discovered, instantiations made, unsupported cases.
- Numeric computation: source spans, extracted quantities, derived facts, comparisons, provenance.
- Solver: route, claim result, negated result, contraposition use, Z3 status, fallback status, unsupported features.
- Proof trace: ordered derivation steps with source IDs.
- Decision: answer, confidence, MCQ local/submission policy used.
- Root cause: category and sanitized message.
- Final status: `ok`, `failed`, or `partial`.

Attribution integrity rule:

- Preserve earliest failure stage. Parser/frame/schema/compiler failures must not be re-labeled later as `solver_capability_gap`.

Root-cause categories should include:

- `candidate_extraction_error`
- `llm_frame_error`
- `frame_validation_error`
- `frame_compile_error`
- `schema_validation_error`
- `normalization_error`
- `quantifier_instantiation_error`
- `numeric_extraction_error`
- `solver_routing_error`
- `solver_capability_gap`
- `proof_search_error`
- `semantic_fallback_used`
- `decision_error`
- `explanation_error`
- `annotation_noise`
- `timeout_error`
- `api_error`

Required artifacts:

- `artifacts/frame_events.jsonl` for parser lifecycle events (`raw_response`, `normalized_frame`, `validated_frame`, `compiled_ast`, `rejected`).
- `artifacts/parser_replay_*.jsonl` for sanitized replay of real parser failures.
- `artifacts/numeric_validation_failures.jsonl` for strict numeric gate failures.
- Sequencing rule: before extractor/live parser exists, artifacts may include only provided/mock-frame events (`normalized_frame`, `validated_frame`, `compiled_ast`, `rejected`); once extractor is active, every LLM parse attempt must include `raw_response`. If credentials/provider are blocked, record blocker/gate status and do not claim pass.

## 12.5 Maintainability Checkpoints

Some batches may add focused maintainability checkpoints after a contract is proven by tests. These checkpoints must preserve runtime behavior and public APIs while reducing file size, improving module boundaries, and strengthening regression coverage.

Batch 8.5 is the numeric-layer maintainability checkpoint. It must split the large Batch 7 numeric layer into focused modules only after Batch 8 has proven the solver handoff and answer-decision contract. It must not add new solver capabilities, change answer behavior, call the LLM, use reference-only fields, or introduce dataset-specific logic.

## 13. Training Use of FOL Annotations

`premises-FOL` can be used offline to:

- evaluate parse-frame extraction quality
- evaluate frame-to-AST compiler quality
- train or tune the frame extractor
- discover common logic fragments
- compare symbolic outputs against references

It must not be used as runtime input during evaluation or submission.

## 14. Recommended Build Order

1. Implement dataset flattening from raw records to one sample per question.
2. Implement runtime-safe flattened loader and reference-field sanitizer.
3. Implement cache keys for local `record_id` and API `premises_hash`.
4. Implement question candidate extraction.
5. Define compact parse-frame schema.
6. Define typed AST schema.
7. Implement deterministic frame-to-AST compiler.
8. Implement AST validation and normalization.
9. Implement LLM parse-frame extractor, repair loop, and cache.
10. Run credential-gated live parser smoke/quality gate; if blocked, record blocker and do not claim pass.
11. Add async sample-level evaluation with bounded LLM concurrency.
12. Add structured debug trace collection.
13. Add numeric extraction and deterministic numeric evaluator.
14. Implement Horn prover, safe contraposition, and bounded quantifier support.
15. Refactor the numeric layer into maintainable focused modules without changing behavior.
16. Add Z3 support for numeric constraints and grounded non-Horn/nested formulas.
17. Add semantic fallback for low-confidence or unsupported cases.
18. Add MCQ, Yes/No/Unknown, and best-effort open-ended answer logic.
19. Generate proof-trace-based explanations.
20. Add API endpoint and `.env` runtime config.
21. Add evaluation scripts for accuracy, explanation grounding, cache stats, and root-cause categories.
