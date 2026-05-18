# MODEL-001 Prompt Intent Baseline Re-evaluation

Date: 2026-05-18

Command:

```bash
python - <<'PY' > /tmp/j3-model-001-baseline-report.json
import json
from pathlib import Path
from j3.prompt_intents import (
    evaluate_prompt_intent_learned_baseline,
    load_prompt_intent_records,
)

records = load_prompt_intent_records(
    Path("../prompts/coding_agent_prompts_expanded_v0.jsonl")
)
report = evaluate_prompt_intent_learned_baseline(records)
print(json.dumps(report, indent=2, sort_keys=True))
PY
```

Corpus:

- Rows: 320 total, 206 train, 42 validation, 72 test.
- Report schema: `prompt-intent-learned-baseline-report-v1`.
- Decision: evaluation only, not wired to production.

## Headline Metrics

| Split | Exact-field accuracy | Clarification accuracy | Ambiguity accuracy | Inferred default precision | Inferred default recall |
| --- | ---: | ---: | ---: | ---: | ---: |
| validation | 10/42 = 0.238 | 40/42 = 0.952 | 40/42 = 0.952 | 0/1 = 0.000 | 0/0 = 0.000 |
| test | 9/72 = 0.125 | 68/72 = 0.944 | 69/72 = 0.958 | 0/1 = 0.000 | 0/1 = 0.000 |

## Field Accuracy

| Split | repo_mode | task_type | domain | expected_action | requires_clarification | primary_artifact | unsupported_requirement | unsupported_requirement_family |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| validation | 0.857 | 0.690 | 0.357 | 0.857 | 0.952 | 0.595 | 1.000 | 1.000 |
| test | 0.944 | 0.736 | 0.236 | 0.889 | 0.944 | 0.750 | 1.000 | 1.000 |

## Residual Groups

The report produced 136 grouped residuals across validation and test.
Largest observed groups begin with domain and artifact confusion:

- test `domain`: `cli -> errors`, 4 rows.
- test `domain`: `auth -> lint`, 2 rows.
- test `domain`: `logs -> text`, 2 rows.
- test `domain`: `paths -> lint`, 2 rows.
- test `domain`: `recipe_box -> bookmark_cli`, 2 rows.

Inferred defaults remain data-limited. The train split has eight inferred
default labels, validation has no positive inferred-default rows, and test has
one unseen positive label, `prefer_value_change_over_key_rename`. The learned
one-vs-rest label baseline therefore records one test false negative and one
test false positive.

## Interpretation

The current learned prompt-intent baseline is useful for detecting
clarification-shaped prompts, but it is not ready as a general intent model.
The main residual families are high-cardinality `domain`, `task_type`, and
`primary_artifact` labels with sparse examples per label. Inferred defaults need
more reviewed examples before precision/recall is meaningful.
