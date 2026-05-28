# Dataset Clarification Answer
## Question
Question ID: `QUESTION_CHOICES_INPUT_POLICY`  
For records with a separate `choices` array, should local evaluation pass `choices` as a runtime input field, or should flattening merge `choices` into the `question` text before inference?

## Answer
Use **flattening to merge `choices` into `question` text before inference**.  
Do **not** add `choices` as a runtime input field.

## Dataset Evidence
- In `docs/flow.md`, runtime-safe input is explicitly constrained to `premises-NL` and `question`, and the flattened runtime input fields are `sample_id`, `record_id`, `question_id`, `premises-NL`, `question`.
- In `docs/competition.md`, evaluation input for Type 1 is also described as question + `premises-NL`, with non-input fields treated as reference annotations.
- Observed raw data includes a separate `choices` field in exactly one record (`record 132`), where:
  - `question`: `Can the variable 'Math' be accessed in the class 'Science_subject'?`
  - `choices`: contains the A/B/C/D option texts
  - `answer`: `A`
- If `choices` is not merged during flattening, candidate extraction from `question` alone would miss options for this record.

## Recommended Plan.md Revision
- Add a flattening rule: when a record has `choices`, serialize them into canonical MCQ lines appended to the question text (e.g., `A. ...`, `B. ...`, `C. ...`, `D. ...`) in stable order.
- Keep runtime schema unchanged (`premises-NL`, `question` only) for both local evaluation and API parity.
- Add validation in flattening/evaluation:
  - assert MCQ answers (`A/B/C/D`) have extractable options after flattening,
  - emit a warning/error artifact when options are missing.
- Add a regression test with record `132`-style input to prevent silent option loss.
