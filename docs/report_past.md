# Dataset Coverage Report
## 1. Dataset Overview
- Files inspected under `data/raw/`: `1` (`Logic_Based_Educational_Queries.json`)
- Docs inspected: `docs/flow.md`, `docs/competition.md`
- Total records: `411`
- Total questions: `808`
- Record keys: `idx`, `premises-FOL`, `premises-NL`, `questions`, `answers`, `explanation` (plus `choices` in record `132` only)
- Per-record questions: min `1`, max `2`, avg `1.966`
- Premises count (`premises-NL`): min `3`, max `36`, avg `10.798`
- Premises count (`premises-FOL`): min `3`, max `36`, avg `10.876`
- Answer distribution: `Yes/No = 416` (`Yes=116`, `No=300`), `Unknown=209`, `MCQ(A/B/C/D)=183`
- MCQ format in question text (`A./B./C./D.` lines): `346` questions (larger than MCQ labels, so some non-MCQ labels still include options)
- Questions containing FOL symbols/tokens (`∀ ∃ ¬ -> ForAll Exists`): `86`
- Structural anomalies:
  - `11` records where `len(premises-NL) != len(premises-FOL)` (e.g., records `34,57,146,334,376-382`)
  - `132` potential answer/explanation conflicts (heuristic: answer says `No` but explanation says statement “true”, etc.)

## 2. Dataset Case Taxonomy
| Case type name | Description | Representative file/row/sample id | Why it matters | What future plan must support |
|---|---|---|---|---|
| Simple factual entailment (Yes/No) | Direct or short-chain entailment check | `Logic_Based_Educational_Queries.json`, `record=1,q=1` | Core majority task | Deterministic entailment + contradiction checks |
| Multiple-choice inference | 4-option candidate verification | `record=0,q=0` | Must score A/B/C/D reliably | Candidate extraction per option + per-option proof scoring |
| Unknown/insufficient evidence | No unique supported conclusion | `record=27,q=0`; `record=28,q=0` | High frequency (`209`) | Internal `Unknown` decision policy and abstention logic |
| Numeric/comparison reasoning | Thresholds, percentages, GPA, credits, durations | `record=34,q=0`; `record=20,q=0`; `record=29,q=0` | Requires arithmetic + comparisons, not only symbolic rules | Numeric frame extraction + evaluator + unit/range validation |
| Negation handling | Explicit negative literals/constraints | `record=4,q=0`; `record=90,q=1` | Wrong polarity flips answers | Preserve explicit negation in parse + solver |
| Conjunction/disjunction | Multi-condition antecedents and “or” branches | `record=23,q=0`; `record=34,q=0` | Proof requires branch and clause integrity | AST for `and/or`, branch-aware verification |
| Conditional/if-then questions | Question itself asks implication validity | `record=0,q=1`; `record=37,q=1` | Need meta-level statement checking | Parse statement-as-claim and verify claim truth |
| Nested/multi-hop chains | Longer premise chains over many facts/rules | `record=28,q=0` (28 premises) | Error accumulation risk | Traceable multi-hop proof, premise selection, confidence penalties |
| Temporal/ordering constraints | before/after/within semester/year/time windows | `record=29,q=0`; `record=34,q=0` | Requires ordering-aware checks | Temporal constraint extraction and evaluation |
| Entity ambiguity/coreference | Same entity across long composite question | `record=34,q=0` | Wrong entity linkage causes false proofs | Entity normalization/coreference safeguards |
| FOL-like question text | Questions/options include symbolic formulas | `record=333,q=0`; `record=334,q=0` | NL-only parser may fail on symbols | Hybrid parser path for symbolic tokens |
| Unusual option format | Options in separate `choices` field (not inline) | `record=132,q=0` | Candidate extraction can miss options | Support both inline options and dedicated `choices` array |
| Annotation inconsistency/noise | Answer/explanation mismatch; premise-count mismatch | `record=37,q=1`; mismatches in `34,57,146,334,376-382` | Affects training and evaluation confidence | Noise-tolerant evaluation, QC flags, conflict-aware metrics |

## 3. Hard / Edge Cases
1. Dataset file: `Logic_Based_Educational_Queries.json`; row/sample id: `record=34,q=0`  
Original input: 27 NL premises about major transfer, GPA/credits/similarity/exam/scholarship/time-limit constraints.  
Question: “Can Mai successfully change majors ... within 1 year ... ?”  
Options: none (free-form yes/no style).  
Answer: `No`.  
Why hard: multi-hop + numeric thresholds + temporal constraints + risk conditions in one long query.  
What Plan.md must support: numeric evaluator, temporal checks, long-context entity tracking, contradiction detection.

2. Dataset file: `Logic_Based_Educational_Queries.json`; row/sample id: `record=132,q=0`  
Original input: OOP access-specifier premises (`Public/Protected/Private`, inheritance).  
Question: “Can the variable 'Math' be accessed in the class 'Science_subject'?”  
Options: stored in `choices` field (not inline in question).  
Answer: `A`.  
Why hard: nonstandard option location; domain-specific terminology.  
What Plan.md must support: dual option extraction path (inline + `choices`), robust domain lexical normalization.

3. Dataset file: `Logic_Based_Educational_Queries.json`; row/sample id: `record=333,q=0`  
Original input: AI-model rule premises.  
Question: MCQ with symbolic options (`∀x`, `¬`, `→`, `∧`).  
Options: inline A/B/C/D symbolic formulas.  
Answer: `Unknown`.  
Why hard: mixed NL+symbolic parsing; solver-ready logical expressions in options.  
What Plan.md must support: symbolic-token-aware parsing and AST compilation fallback.

4. Dataset file: `Logic_Based_Educational_Queries.json`; row/sample id: `record=37,q=1`  
Original input: existential/universal student premises.  
Question: implication truth statement (“If there exists ... then there exists ...”).  
Options: none.  
Answer: `No`; explanation text says statement is true.  
Why hard: annotation conflict.  
What Plan.md must support: label-noise handling, conflict auditing, evaluation modes that separate model error vs annotation inconsistency.

5. Dataset file: `Logic_Based_Educational_Queries.json`; row/sample id: `record=376` (also `377-382`)  
Original input: Vietnamese-name academic policy records with premise count mismatch (`premises-NL=13`, `premises-FOL=22` for 376).  
Question: MCQ + yes/no pair.  
Options: inline A/B/C/D.  
Answer: e.g., `['A','Yes']` for 376.  
Why hard: schema inconsistency between NL and FOL references.  
What Plan.md must support: runtime-only dependence on NL premises; strict schema validators; anomaly logs.

## 4. Requirements Missing or Unclear in Source Docs
- `docs/competition.md` states Type-1 dataset has `464 records / 913 questions`, but actual raw file inspected is `411 / 808`. Release/version alignment is unclear.
- Canonical label policy is unclear in competition doc (`Unknown` vs `Uncertain`), while flow doc defines `Unknown` canonical + alias handling.
- MCQ option source format is underspecified (inline options vs separate `choices` field observed in record `132`).
- Handling policy for annotation noise (answer/explanation contradictions, FOL/NL premise count mismatch) is not explicitly specified.
- Evaluation fallback policy for unresolved MCQ (no provable option or multiple provable options) is detailed in flow doc but not in competition doc.

## 5. Coverage Requirements for Plan.md
- requirement id: `CR-001`  
  requirement: Support both record-level multi-question format and flattened per-question runtime samples.  
  evidence from dataset: all 411 records contain question arrays (1–2 each), total 808 questions.  
  affected planning area: data ingestion + preprocessing.  
  priority: high.

- requirement id: `CR-002`  
  requirement: Candidate extraction must parse MCQ from both inline `A/B/C/D` text and optional `choices` array.  
  evidence from dataset: record `132` includes `choices`; 346 questions include inline option markers.  
  affected planning area: candidate extraction.  
  priority: high.

- requirement id: `CR-003`  
  requirement: Decision layer must natively support `Yes/No/Unknown` plus MCQ `A/B/C/D`.  
  evidence from dataset: answers = `Yes/No` 416, `Unknown` 209, MCQ 183.  
  affected planning area: answer decision + scoring adapter.  
  priority: high.

- requirement id: `CR-004`  
  requirement: Numeric reasoning path for thresholds/comparisons/temporal windows.  
  evidence from dataset: numeric/threshold style questions (e.g., records `20,29,34`).  
  affected planning area: parser schema + numeric evaluator + solver routing.  
  priority: high.

- requirement id: `CR-005`  
  requirement: Preserve explicit negation, conjunction/disjunction, and conditionals during parse and solve.  
  evidence from dataset: frequent logical markers (conditional 336, negation 299, conjunction 212, disjunction 16 by question-text heuristic).  
  affected planning area: frame schema + AST + symbolic verifier.  
  priority: high.

- requirement id: `CR-006`  
  requirement: Handle symbolic/FOL-like question text and options.  
  evidence from dataset: 86 questions contain FOL symbols/tokens; example records `333,334`.  
  affected planning area: parser robustness + AST compilation.  
  priority: medium.

- requirement id: `CR-007`  
  requirement: Add dataset anomaly detection and QC tagging (not hard-fail runtime).  
  evidence from dataset: 11 premise-count mismatch records; 132 potential answer/explanation conflicts.  
  affected planning area: validation + evaluation + debugging artifacts.  
  priority: high.

- requirement id: `CR-008`  
  requirement: Implement unknown/insufficient-evidence policy and abstention confidence logic.  
  evidence from dataset: `Unknown` is 209/808 (~25.9%).  
  affected planning area: answer decision + calibration.  
  priority: high.

## 6. Architecture Risks
- Annotation-noise risk: training/eval can overfit inconsistent labels or contradictory explanations.
- Parser fragility risk: mixed NL, symbolic tokens, and long conditional chains can cause frame invalidity.
- Candidate-extraction risk: missing `choices`-field handling can silently drop valid options.
- Numeric/temporal misrouting risk: if routed to generic symbolic-only path, threshold/time questions fail.
- Over-reliance on reference fields risk: runtime must never depend on `premises-FOL`, `answer`, `explanation`, `idx`.
- Version drift risk: documented dataset size (464/913) differs from current file (411/808), affecting benchmark comparability.

## 7. Recommended Planning Guidance
- Treat `premises-NL + question` as sole runtime inputs; enforce sanitizer tests that block reference-field access.
- Build strict but fault-tolerant ingestion: schema validation + anomaly tagging + continue processing.
- Implement two candidate extraction modes: inline MCQ parsing and explicit `choices` parsing.
- Route reasoning by capability: symbolic core + numeric/temporal evaluator + unknown fallback.
- Add conflict-aware evaluation reports separating model failures from annotation inconsistencies.
- Track dataset-version metadata in artifacts so results are reproducible against `411/808` current snapshot.
