from __future__ import annotations

import json

from j3.actions import PatchAction, PatchActionKind, PatchTarget
from j3.failure_hints import AssertionComparison, PytestFailureHint, TracebackLocation
from j3.synth import SourceEdit
from j3.transition_scorer_advice import (
    build_transition_scorer_advice,
    format_transition_scorer_advice_summary,
    summarize_transition_scorer_advice,
    transition_scorer_ranked_candidates,
)
from repair.patching.types import CandidatePatch


def test_summarize_transition_scorer_advice_reports_shadow_metrics(tmp_path) -> None:
    advice = tmp_path / "transition-advice.jsonl"
    rows = [
        _advice_row(
            candidate_count=3,
            selected={"id": "candidate-2", "rank_index": 2, "validated": True, "passed": True},
            scorer_top={
                "id": "candidate-1",
                "rank_index": 1,
                "validated": True,
                "passed": False,
            },
            comparison={
                "known": True,
                "would_have": "regressed",
                "existing_first_passing_index": 2,
                "scorer_first_known_passing_position": 3,
            },
        ),
        _advice_row(
            candidate_count=2,
            selected={"id": "candidate-a", "rank_index": 1, "validated": True, "passed": True},
            scorer_top={
                "id": "candidate-a",
                "rank_index": 1,
                "validated": True,
                "passed": True,
            },
            comparison={
                "known": True,
                "would_have": "same",
                "existing_first_passing_index": 1,
                "scorer_first_known_passing_position": 1,
            },
        ),
        _advice_row(
            candidate_count=4,
            selected={"id": "candidate-z", "rank_index": 3, "validated": True, "passed": True},
            scorer_top={
                "id": "candidate-y",
                "rank_index": 2,
                "validated": True,
                "passed": True,
            },
            comparison={
                "known": True,
                "would_have": "improved",
                "existing_first_passing_index": 3,
                "scorer_first_known_passing_position": 1,
            },
        ),
    ]
    advice.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )

    summary = summarize_transition_scorer_advice([advice])
    record = summary.as_dict()

    assert record["schema_version"] == "transition-scorer-advice-summary-v1"
    assert record["advice_paths"] == [str(advice.resolve())]
    assert record["advice_row_count"] == 3
    assert record["candidate_count"] == 9
    assert record["scorer_production_agreement"] == {
        "count": 1,
        "total": 3,
        "rate": 0.333333,
    }
    assert record["known_validation"] == {
        "row_count": 3,
        "improved_count": 1,
        "regressed_count": 1,
        "no_change_count": 1,
        "production_pass_at_1_count": 3,
        "production_pass_at_1_rate": 1.0,
        "scorer_pass_at_1_count": 2,
        "scorer_pass_at_1_rate": 0.666667,
        "average_candidates_saved_or_lost": 0.333333,
    }
    assert record["runtime"]["hosted_llm_api_calls"] == 0
    assert record["usage"]["hosted_llm_prompt_tokens"] == 0
    assert record["usage"]["hosted_repo_context_bytes"] == 0

    output = format_transition_scorer_advice_summary(summary)
    assert "j3 summarize-transition-advice" in output
    assert "advice rows: 3" in output
    assert "candidates: 9" in output
    assert "scorer/production agreement: 1/3 (33.33%)" in output
    assert "known validation: improved=1 regressed=1 no_change=1" in output
    assert "production-selected pass@1: 3/3 (100.00%)" in output
    assert "scorer-top pass@1: 2/3 (66.67%)" in output
    assert "average candidates saved/lost: 0.33" in output
    assert "hosted_llm_api_calls: 0" in output
    assert "hosted_repo_context_bytes: 0" in output


def test_ranked_candidates_demote_unvalidated_add_keyword_decoy_without_hint() -> None:
    add_keyword = _patch_candidate(
        kind=PatchActionKind.ADD_KEYWORD_ARG,
        params={"keyword": "timeout", "value": True, "callee": "fetch"},
        patched_source="def load():\n    return fetch(timeout=True)\n",
        model_score=1.0,
        ranker_score=1.0,
        failure_hint_score=1.0,
    )
    literal = _patch_candidate(
        kind=PatchActionKind.CHANGE_LITERAL,
        params={"to": 30},
        patched_source="def load():\n    return fetch(30)\n",
        model_score=0.0,
        ranker_score=0.0,
        failure_hint_score=0.0,
    )

    ranked = transition_scorer_ranked_candidates([add_keyword, literal])

    assert ranked == (literal, add_keyword)


def test_ranked_candidates_keep_add_keyword_when_hint_names_missing_keyword() -> None:
    add_keyword = _patch_candidate(
        kind=PatchActionKind.ADD_KEYWORD_ARG,
        params={"keyword": "timeout", "value": True, "callee": "fetch"},
        patched_source="def load():\n    return fetch(timeout=True)\n",
        model_score=1.0,
        ranker_score=1.0,
        failure_hint_score=1.0,
    )
    literal = _patch_candidate(
        kind=PatchActionKind.CHANGE_LITERAL,
        params={"to": 30},
        patched_source="def load():\n    return fetch(30)\n",
        model_score=0.0,
        ranker_score=0.0,
        failure_hint_score=0.0,
    )

    ranked = transition_scorer_ranked_candidates(
        [add_keyword, literal],
        candidate_hints=[
            (PytestFailureHint(type_error_names={"timeout"}),),
            (),
        ],
    )

    assert ranked == (add_keyword, literal)


def test_ranked_candidates_use_same_mapping_key_value_target_evidence() -> None:
    key_decoy = _patch_candidate(
        kind=PatchActionKind.CHANGE_DICT_KEY,
        params={"from": "secure", "to": "__Secure-"},
        patched_source="def load():\n    return {'__Secure-': True}\n",
        model_score=1.0,
        ranker_score=1.0,
        failure_hint_score=1.0,
        target_context={
            "mapping_name": "attrs",
            "dict_key_from": "secure",
            "dict_key_from_in_same_mapping": True,
            "dict_key_to": "__Secure-",
        },
    )
    value_candidate = _patch_candidate(
        kind=PatchActionKind.CHANGE_DICT_VALUE,
        params={"key": "secure", "from": True, "to": False},
        patched_source="def load():\n    return {'secure': False}\n",
        model_score=0.0,
        ranker_score=0.0,
        failure_hint_score=0.0,
        target_context={
            "mapping_name": "attrs",
            "dict_value_key": "secure",
            "dict_value_key_in_same_mapping": True,
        },
    )
    hints = (
        PytestFailureHint(
            asserted_mapping_keys={"secure"},
            assertions=[
                AssertionComparison(actual=True, operator="is", expected=False)
            ],
        ),
    )

    ranked = transition_scorer_ranked_candidates(
        [key_decoy, value_candidate],
        candidate_hints=[hints, hints],
    )

    assert ranked == (value_candidate, key_decoy)


def test_ranked_candidates_use_module_constant_file_and_name_alignment() -> None:
    literal_neighbor = _patch_candidate(
        kind=PatchActionKind.CHANGE_LITERAL,
        params={"from": 4999, "to": 5000},
        patched_source="def shipping_total():\n    return 5000\n",
        model_score=0.7,
        ranker_score=0.7,
        failure_hint_score=0.7,
        file_path="shop/cart.py",
        symbol="shipping_total",
    )
    module_constant = _patch_candidate(
        kind=PatchActionKind.CHANGE_MODULE_CONSTANT,
        params={
            "name": "FREE_SHIPPING_MINIMUM_CENTS",
            "from": 4999,
            "to": 5000,
        },
        patched_source=(
            "FREE_SHIPPING_MINIMUM_CENTS = 5000\n\n"
            "def shipping_total():\n"
            "    return FREE_SHIPPING_MINIMUM_CENTS\n"
        ),
        model_score=0.0,
        ranker_score=0.0,
        failure_hint_score=0.0,
        file_path="shop/shipping.py",
        symbol="FREE_SHIPPING_MINIMUM_CENTS",
        node_kind="Constant",
    )
    hints = (
        PytestFailureHint(
            traceback_locations=[TracebackLocation(file_path="shop/shipping.py", line=2)],
            function_names={"shipping_total"},
            missing_names={"FREE_SHIPPING_MINIMUM_CENTS"},
            assertions=[
                AssertionComparison(actual=4999, operator="==", expected=5000)
            ],
        ),
    )

    ranked = transition_scorer_ranked_candidates(
        [literal_neighbor, module_constant],
        candidate_hints=[hints, hints],
        context={
            "task": "free_shipping_threshold_module_constant",
            "task_family": "module_constant",
        },
    )

    assert ranked == (module_constant, literal_neighbor)


def test_advice_records_keyword_hint_fields_and_remains_shadow_only(tmp_path) -> None:
    add_keyword = _patch_candidate(
        kind=PatchActionKind.ADD_KEYWORD_ARG,
        params={"keyword": "timeout", "value": True, "callee": "fetch"},
        patched_source="def load():\n    return fetch(timeout=True)\n",
        model_score=1.0,
        ranker_score=1.0,
        failure_hint_score=1.0,
    )
    literal = _patch_candidate(
        kind=PatchActionKind.CHANGE_LITERAL,
        params={"to": 30},
        patched_source="def load():\n    return fetch(30)\n",
        model_score=0.0,
        ranker_score=0.0,
        failure_hint_score=0.0,
    )

    advice = build_transition_scorer_advice(
        repo=tmp_path,
        test_command="python -m pytest",
        baseline_exit_code=1,
        candidates=[add_keyword, literal],
        selected=literal,
        tested_candidates=[literal],
        passing_candidates=[literal],
        candidate_hints=[
            (PytestFailureHint(missing_keys={"timeout"}),),
            (),
        ],
        first_passing_index=2,
    )

    assert advice["mode"] == "shadow"
    assert advice["decision"] == "shadow_only_not_wired_to_routing"
    assert advice["scorer_ranked_candidate_ranks"] == [1, 2]
    assert advice["scorer_top_candidate"]["action"] == "add_keyword_arg"


def _advice_row(
    *,
    candidate_count: int,
    selected: dict[str, object],
    scorer_top: dict[str, object],
    comparison: dict[str, object],
) -> dict[str, object]:
    usage = {
        "hosted_llm_api_calls": 0,
        "hosted_llm_prompt_tokens": 0,
        "hosted_llm_completion_tokens": 0,
        "hosted_api_tokens": 0,
        "hosted_repo_context_bytes": 0,
    }
    return {
        "schema_version": "transition-scorer-advice-v1",
        "mode": "shadow",
        "decision": "shadow_only_not_wired_to_routing",
        "candidate_count": candidate_count,
        "existing_selected_candidate": selected,
        "scorer_top_candidate": scorer_top,
        "validation_comparison": comparison,
        "runtime": {"local_runtime_ms": 1.5, **usage},
        "usage": usage,
    }


def _patch_candidate(
    *,
    kind: PatchActionKind,
    params: dict[str, object],
    patched_source: str,
    model_score: float,
    ranker_score: float,
    failure_hint_score: float,
    target_context: dict[str, object] | None = None,
    file_path: str = "client.py",
    symbol: str = "load",
    node_kind: str = "Call",
) -> CandidatePatch:
    original_source = "def load():\n    return fetch()\n"
    return CandidatePatch(
        file_path=file_path,
        action=PatchAction(
            kind=kind,
            target=PatchTarget(
                file_path=file_path,
                start_line=2,
                end_line=2,
                symbol=symbol,
                node_kind=node_kind,
            ),
            params=params,
        ),
        edit=SourceEdit(
            start_line=2,
            start_col=11,
            end_line=2,
            end_col=18,
            replacement=patched_source.splitlines()[1].strip(),
        ),
        original_source=original_source,
        patched_source=patched_source,
        reason=f"try {kind.value}",
        model_score=model_score,
        failure_hint_score=failure_hint_score,
        ranker_score=ranker_score,
        target_context=(
            dict(target_context)
            if target_context is not None
            else {"function_name": symbol, "line_span": [2, 2]}
        ),
    )
