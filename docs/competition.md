# EXACT 2026 Competition

## Introduction

Large Language Models (LLMs) have demonstrated impressive abilities in question-answering systems, including those applied in educational contexts. However, these models often generate only brief, single-answer responses without providing any reasoning or explanatory detail. In educational environments, this lack of transparency poses significant challenges:

### Quality of Answers

When an answer is incorrect, we cannot trace or understand the source of the error. When it is correct, we have no visibility into how it was derived or whether it was properly verified.

### Complex Reasoning

Educational domains often involve intricate rules, policies, and multi-step logical reasoning, which can be challenging for purely data-driven LLMs to handle reliably.

One promising direction within Explainable AI (XAI) is **Symbolic Reasoning**, where a Symbolic Engine, either standalone or integrated with an LLM, makes the reasoning process explicit. However, many other approaches can also achieve transparency. This challenge invites any method that enhances both the accuracy and interpretability of educational Question Answering (QA) systems, making them more suitable for verifiable use in learning environments.

## Example Queries

The following examples illustrate the types of educational queries this challenge addresses, along with expected transparent responses:

| Query | Expected Response |
| --- | --- |
| This semester, I scored 8 points on the final exam for the DSA course. However, I was absent for the lab exam. Can I still get a B in this course? | No. Because you missed the lab exam, you received a score of 0 for lab work. According to Regulation #13 of X University, a student with 0 lab points cannot pass the course. |

The primary goal of this challenge is to build educational QA systems that not only produce accurate answers but also provide clear, verifiable reasoning for how those answers were derived.

Specifically, we seek to:

- Encourage, but not require, the use of symbolic reasoning tools such as Z3, custom solvers, or other logic-based engines alongside LLMs.
- Provide benchmark datasets and evaluation frameworks to support future developments in explainable AI for education.

## What You'll Build

Participating teams will develop systems that:

- Provide correct final answers to educational queries.
- Generate natural language explanations that justify each answer.
- Optionally provide additional supporting evidence, such as First-Order Logic (FOL) derivations, Chain-of-Thought (CoT) reasoning, premise lists, or other structured proofs, to strengthen the system's reasoning depth.
- Use any approach, including symbolic reasoning, neurosymbolic methods, fine-tuned LLMs, or any combination, as long as the system can explain how it arrived at each answer.

## Challenge Chairs

The quality and fairness of this challenge are ensured by an international committee of professors and experts:

- Prof. Quan Thanh Tho, Ho Chi Minh City University of Technology (HCMUT), Vietnam
- Prof. Emanuel Di Nardo, University of Naples Parthenope, Italy
- Prof. Nguyen Duc Anh, Department of IT and Economics, University of South Eastern Norway, Norway
- Prof. Fabien Baldacci, Universite de Bordeaux, France
- Prof. Nguyen Le Minh, Japan Advanced Institute of Science and Technology (JAIST), Japan

## Competition Rules

### Who Can Participate

This competition is open to everyone: high school students, university students, working professionals, and researchers worldwide. There is no restriction on age, nationality, or affiliation, except that members of the URA Research Group, the organizing team, are not eligible to participate.

### Rules

All participating teams must adhere to the following rules throughout the competition.

#### Do

**Provide Explainable Answers**

Every generated answer must be accompanied by a natural language explanation that justifies how the answer was derived. The explanation should be concise, interpretable, and verifiable.

**Use a Symbolic Engine, Encouraged**

Teams are encouraged to incorporate symbolic reasoning, such as Z3 Solver or a custom-built engine, to verify and explain answers. However, this is not mandatory. Any approach that produces explainable results is accepted.

**Use Open-Source LLMs**

All LLMs used in the system must be open-source and have 8 billion parameters or fewer. This applies to any LLM component, whether used for answer generation, reasoning, or Natural Language to Logic conversion.

#### Do Not

**Use Closed-Source Models**

The use of commercial or closed-source LLMs, such as GPT, Claude, or Gemini, is strictly prohibited. Submissions that rely on closed-source models will be disqualified.

**Hide External Data Sources**

All external datasets used for fine-tuning LLMs or Symbolic Engines must be fully disclosed. Failure to disclose external data usage will result in disqualification.

## Datasets

The official datasets will be released at the kick-off workshop. Dataset types will be provided, covering logical reasoning in educational regulations

The input provided to each team's system depends on the dataset type. All other fields, such as FOL, CoT, explanations, and related annotations shown in the samples, are reference annotations provided in the training data only. Teams can use them as templates for building their own reasoning pipelines.

### Dataset Type 1: Logic-Based Educational Queries

This dataset contains 464 records with a total of 913 questions designed to evaluate logical reasoning in educational contexts.

Topics cover university regulations such as grading policies, course enrollment rules, scholarship criteria, and academic requirements. Question types include Multiple Choice, Yes/No/Uncertain, and open-ended queries.

Each record includes a set of premises in both natural language and FOL, along with derived questions, ground-truth answers, and human-written explanations. During evaluation, the system receives the question together with the natural language premises (`premises-NL`) as input. Teams are free to use the premises in any way, such as prompt context or FOL conversion.

```json
{
  "premises-NL": [
    "If a curriculum is well-structured and has exercises, it enhances student engagement.",
    "If a curriculum enhances student engagement and provides access to advanced resources, it enhances critical thinking.",
    "If a faculty prioritizes pedagogical training and curriculum development, the curriculum is well-structured.",
    "The faculty prioritizes pedagogical training and curriculum development.",
    "The curriculum has practical exercises.",
    "The curriculum provides access to advanced resources."
  ],
  "premises-FOL": [
    "ForAll(c, (well_structured(c) AND has_exercises(c)) -> enhances_engagement(c))",
    "ForAll(c, (enhances_engagement(c) AND advanced_resources(c)) -> enhances_critical_thinking(c))",
    "..."
  ],
  "questions": [
    "Based on the premises, what can we conclude about the curriculum?\nA. It enhances student engagement but not critical thinking\nB. It enhances critical thinking\nC. It needs more resources to enhance critical thinking\nD. It is well-structured but lacks exercises",
    "Does the combination of faculty priorities and curriculum features lead to enhanced critical thinking?"
  ],
  "answers": ["B", "Yes"],
  "explanation": [
    "Premise 4 and premise 3 confirm the curriculum is well-structured. Premise 5 provides exercises, so premise 1 implies enhanced engagement. Premise 6 adds advanced resources, and premise 2 confirms enhanced critical thinking, supporting option B.",
    "Faculty priorities satisfy premise 3, making the curriculum well-structured. Exercises (premise 5) and premise 1 lead to enhanced engagement, and with advanced resources (premise 6), premise 2 confirms enhanced critical thinking."
  ]
}
```

## Evaluation Criteria

Submissions are assessed across three dimensions: correctness, explanation quality, and reasoning depth.

| Criterion | Description |
| --- | --- |
| P1: Correctness of Answers | Generating accurate and precise answers for the given queries. |
| P2: Quality of Explanation | Providing a clear, coherent natural language explanation that justifies the answer. |
| P3: Depth of Reasoning | Demonstrating strong reasoning capabilities through additional supporting evidence, such as FOL derivations, CoT steps, premise identification, or other structured proofs. |

## Test Format

The official test set will combine both dataset types into a single unified set.

For Type 1 queries, the system receives the question along with natural language premises. Questions will include multiple-choice, Yes/No/Uncertain, open-ended reasoning, and numerical computation problems.

The topic distribution, including the percentage of each dataset type, will be announced at the kick-off workshop.

## Evaluation Process

**Phase 1 and Phase 2: Selection**

Submissions are first scored automatically against ground-truth answers, then reviewed by the organizing committee for explanation quality.

**Final Round**

Top teams run their systems live on unseen queries. The Challenge Chairs evaluate each team's answers, explanations, and reasoning depth in real time. Teams demonstrating stronger reasoning capabilities will be ranked higher.

**Final Score**

The final score will be computed as a weighted combination of P1, P2, and P3. Specific weights will be published with the official dataset release.

## Submission Requirements

Each team must submit an API endpoint along with a brief solution description, up to 1 page, detailing their approach, models used, and the dataset used for training.

For each query, the API must return the required fields below. Teams are encouraged to include optional fields that demonstrate the depth of their system's reasoning. Richer evidence will have an advantage in the evaluation, particularly in the final round where the Challenge Chairs assess reasoning depth live.
Example response: 
```json 
{
  "answer": "B",
  "explanation": "The voltage across R2 is calculated using ...",
  "fol": "For all x, Resistor(x) -> HasVoltage(x, V)",
  "cot": [
    "Step 1: Identify the circuit topology ...",
    "Step 2: Apply Kirchhoff's voltage law ...",
    "Step 3: Solve for the unknown voltage ..."
  ],
  "premises": [
    "Ohm's law: V = IR",
    "KVL: sum of voltages in a loop = 0"
  ],
  "confidence": 0.92
}
```

The final submission format will be finalized at the kick-off workshop.
