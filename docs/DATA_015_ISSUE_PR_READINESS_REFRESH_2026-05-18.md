# DATA-015 Issue/PR Readiness Refresh

Readiness scoring only; no candidate source edits were attempted.
This refresh includes the DATA-013 Click semver prompt/spec evidence.

Result: `pallets__click-issue-3298-pr-3299` is now
`ready_for_candidate_attempt`; no missing-evidence labels remain for any of the
first three replay rows. The next recommended candidate attempt is
`pallets__click-issue-3298-pr-3299` after the in-flight DATA-014 Click
default-map attempt is reviewed.

## Summary

- Rows: `3`
- Status counts: `{"ready":3}`
- Missing evidence: `{}`
- Next-stage challenges: `{"materialization_gap":3,"ranking_gap":3}`
- Ready replay ids: `["psf__requests-issue-7432-pr-7433","pallets__click-issue-2745-pr-3364","pallets__click-issue-3298-pr-3299"]`

## Rows

| Replay | Repo | Ready | Missing evidence | Validation command | Recommendation |
| --- | --- | --- | --- | --- | --- |
| `psf__requests-issue-7432-pr-7433` | `psf/requests` | `true` | `none` | `.venv/bin/python -m pytest tests/test_requests.py -q -k 'prepare_body or rewind_body or getattr_proxy_stream_follows_redirect'` | `ready_for_candidate_attempt; next_stage_challenge=materialization_gap,ranking_gap` |
| `pallets__click-issue-2745-pr-3364` | `pallets/click` | `true` | `none` | `pytest tests/test_defaults.py -q` | `ready_for_candidate_attempt; next_stage_challenge=materialization_gap,ranking_gap` |
| `pallets__click-issue-3298-pr-3299` | `pallets/click` | `true` | `none` | `pytest tests/test_options.py -q` | `ready_for_candidate_attempt; next_stage_challenge=materialization_gap,ranking_gap` |

## Evidence

### `psf__requests-issue-7432-pr-7433`

- Allowed write scope: `{"paths":["src/requests/models.py","tests/test_requests.py"],"policy":"candidate_attempt_must_stay_within_accepted_change_paths","source_paths":["src/requests/models.py"],"test_paths":["tests/test_requests.py"]}`
- Residual labels: `["materialization_gap","ranking_gap"]`
- Next-stage challenge labels: `["materialization_gap","ranking_gap"]`
- Evidence: `prompt_spec` `prompt-spec/psf__requests-issue-7432-pr-7433/requests_prepare_body_getattr_stream` from `/private/tmp/j3-data-011-requests-prepare-body-spec.jsonl`
- Evidence: `validation` `DATA-008/psf__requests-issue-7432-pr-7433/requests-focused-prepare-body-httpbin` from `/private/tmp/j3-data-008-live/attempts.jsonl`
- Evidence: `local_knowledge` `c501bc67cad129b16ceaf5d6c0e3f5c52bcaf74db79ea54de0fe70083664ab9b` from `/private/tmp/j3-know-005-requests-records.jsonl`
- Evidence: `local_knowledge` `3f38b74320eb4c17f12cc4e805de8b86b584aa365718bc0c31946ae581d9c196` from `/private/tmp/j3-know-005-requests-records.jsonl`
- Evidence: `local_knowledge` `374b4a3983980b31fae20ece5cd401b1635a037f67d24011ce53c5c4c32ab152` from `/private/tmp/j3-know-005-requests-records.jsonl`
- Evidence: `local_knowledge` `1b186ed9dc6ecd445dcaab0fbfcdff835392303953bf0aabb2b166737367b1f6` from `/private/tmp/j3-know-005-requests-records.jsonl`
- Evidence: `local_knowledge` `11e680b41a6e8fb921dc30aead5f3c151f6c835cd869e44883d4c0edd22721a3` from `/private/tmp/j3-know-005-requests-records.jsonl`
- Evidence: `local_knowledge` `2a65995299dde502ea0dd8479aaf06930314c4f20caf1dc9ca18a39f746e05c6` from `/private/tmp/j3-know-005-requests-records.jsonl`
- Evidence: `local_knowledge` `0c0bc90547a7ee33dd448c30949761ba932de3ef8d49e3ae62c6a6f63cf352c6` from `/private/tmp/j3-know-005-requests-records.jsonl`

### `pallets__click-issue-2745-pr-3364`

- Allowed write scope: `{"paths":["CHANGES.rst","docs/commands.md","docs/conf.py","src/click/core.py","tests/test_defaults.py"],"policy":"candidate_attempt_must_stay_within_accepted_change_paths","source_paths":["CHANGES.rst","docs/commands.md","docs/conf.py","src/click/core.py"],"test_paths":["tests/test_defaults.py"]}`
- Residual labels: `["materialization_gap","ranking_gap"]`
- Next-stage challenge labels: `["materialization_gap","ranking_gap"]`
- Evidence: `prompt_spec` `prompt-spec/pallets__click-issue-2745-pr-3364/click_default_map_multi_value_parameter` from `/private/tmp/j3-data-009-click-default-map-spec.jsonl`
- Evidence: `validation` `DATA-006/pallets__click-issue-2745-pr-3364/baseline_validation` from `/private/tmp/j3-data-007-blocker-drilldown/outcomes.jsonl`

### `pallets__click-issue-3298-pr-3299`

- Allowed write scope: `{"paths":["src/click/core.py","tests/test_options.py"],"policy":"candidate_attempt_must_stay_within_accepted_change_paths","source_paths":["src/click/core.py"],"test_paths":["tests/test_options.py"]}`
- Residual labels: `["materialization_gap","ranking_gap"]`
- Next-stage challenge labels: `["materialization_gap","ranking_gap"]`
- Evidence: `prompt_spec` `prompt-spec/pallets__click-issue-3298-pr-3299/click_semver_non_string_default_help` from `/private/tmp/j3-data-013-click-semver-spec.jsonl`
- Evidence: `validation` `DATA-006/pallets__click-issue-3298-pr-3299/baseline_validation` from `/private/tmp/j3-data-007-blocker-drilldown/outcomes.jsonl`
- Evidence: `local_knowledge` `1904a6fa15665899650dbaec21829fdac4fdc493daddef9f118928262649d73a` from `/private/tmp/j3-know-004-click-records.jsonl`
- Evidence: `local_knowledge` `637634d1dee21f7cb4dbc244ebe384a4d8c75fb8070735345fac822cdb16ee7a` from `/private/tmp/j3-know-004-click-records.jsonl`
- Evidence: `local_knowledge` `9ec7175c0affa313906dcae73c5304d2dd6bfe1853cfdc05aa4273ebf0948147` from `/private/tmp/j3-know-004-click-records.jsonl`
- Evidence: `local_knowledge` `311aef2b41343232a5491c610f636efdf966891f32767d5e3a574ddc64ded546` from `/private/tmp/j3-know-004-click-records.jsonl`
- Evidence: `local_knowledge` `0dde986e749141c71f592950b9d7518adcb72b4447c488329df813b418bbdd99` from `/private/tmp/j3-know-004-click-records.jsonl`
- Evidence: `local_knowledge` `2882ec4082f4ea978c942600690cf8b99b95bcc92c921293ed6e637f441e67a0` from `/private/tmp/j3-know-004-click-records.jsonl`
- Evidence: `local_knowledge` `f96ac571dae6b2a53647803ebd07d034e91895a038ab1bb19ba6d528d97f7587` from `/private/tmp/j3-know-004-click-records.jsonl`
- Evidence: `local_knowledge` `29bde1f5e4eed1864b02359519d15579d45e2e5c0d697aece2772004f2eed2f1` from `/private/tmp/j3-know-004-click-records.jsonl`

## Artifacts

- JSONL: `/private/tmp/j3-data-015-readiness.jsonl`
