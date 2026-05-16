from __future__ import annotations

import json

from actions import PatchAction, PatchActionKind, PatchTarget
from candidate_ranking import CandidateRankerModel, train_candidate_ranker
from failure_hints import PytestFailureHint
from patching import CandidatePatch, prioritize_candidate_patches, rank_with_candidate_ranker
from synth import SourceEdit


def test_train_candidate_ranker_from_diagnostics_and_rerank(tmp_path) -> None:
    diagnostics = tmp_path / "diagnostics.json"
    diagnostics.write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "name": "boundary",
                        "ranked": {
                            "selected": {"passed": True},
                            "failure_hints": [
                                {
                                    "function_names": ["meets_minimum"],
                                    "source_files": ["bugs.py"],
                                    "assertions": [{"operator": "is", "actual": False, "expected": True}],
                                }
                            ],
                            "tested_candidates": [
                                _candidate_record(to="<", passed=False),
                                _candidate_record(to=">=", passed=True),
                            ],
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    result = train_candidate_ranker(diagnostics_paths=[diagnostics], out_dir=tmp_path / "run")
    ranker = CandidateRankerModel.load(result.ranker_path)
    ranked = rank_with_candidate_ranker(
        [
            _candidate(to="<", failure_hint_score=50.0),
            _candidate(to=">=", failure_hint_score=50.0),
        ],
        ranker,
        hints=[],
    )

    assert result.training_pairs == 1
    assert result.training_accuracy == 1.0
    assert result.margin_violations == 0
    assert ranked[0].action.params["to"] == ">="
    assert ranked[0].ranker_score is not None


def test_ranker_overrides_higher_failure_hint_score(tmp_path) -> None:
    ranker = CandidateRankerModel(
        path=tmp_path / "ranker.json",
        weights={"failure_hint_score": -100.0},
    )
    ranked = prioritize_candidate_patches(
        [
            _candidate(to="<", failure_hint_score=0.0, symbol="meets_minimum"),
            _candidate(to=">=", failure_hint_score=0.0, symbol="other_minimum"),
        ],
        hints=[PytestFailureHint(function_names={"meets_minimum"})],
        ranker=ranker,
    )

    assert ranked[0].action.params["to"] == ">="
    assert ranked[1].failure_hint_score > ranked[0].failure_hint_score
    assert ranked[0].ranker_score is not None
    assert ranked[0].ranker_score > (ranked[1].ranker_score or 0.0)


def test_hint_first_ordering_is_preserved_without_ranker() -> None:
    ranked = prioritize_candidate_patches(
        [
            _candidate(to="<", failure_hint_score=0.0, symbol="meets_minimum"),
            _candidate(to=">=", failure_hint_score=0.0, symbol="other_minimum", ranker_score=100.0),
        ],
        hints=[PytestFailureHint(function_names={"meets_minimum"})],
    )

    assert ranked[0].action.params["to"] == "<"
    assert ranked[0].failure_hint_score > ranked[1].failure_hint_score


def _candidate_record(*, to: str, passed: bool) -> dict[str, object]:
    return {
        "file_path": "bugs.py",
        "action": "change_operator",
        "symbol": "meets_minimum",
        "start_line": 2,
        "end_line": 2,
        "params": {"from": ">", "to": to},
        "reason": f"try comparison operator {to}",
        "model_score": 0.5,
        "failure_hint_score": 50.0,
        "ranker_score": None,
        "passed": passed,
    }


def _candidate(
    *,
    to: str,
    failure_hint_score: float,
    symbol: str = "meets_minimum",
    ranker_score: float | None = None,
) -> CandidatePatch:
    source = "def meets_minimum(value, minimum):\n    return value > minimum\n"
    return CandidatePatch(
        file_path="bugs.py",
        action=PatchAction(
            kind=PatchActionKind.CHANGE_OPERATOR,
            target=PatchTarget(
                file_path="bugs.py",
                start_line=2,
                end_line=2,
                symbol=symbol,
                node_kind="Compare",
            ),
            params={"from": ">", "to": to},
        ),
        edit=SourceEdit(start_line=2, start_col=11, end_line=2, end_col=26, replacement=f"value {to} minimum"),
        original_source=source,
        patched_source=source.replace("value > minimum", f"value {to} minimum"),
        reason=f"try comparison operator {to}",
        model_score=0.5,
        failure_hint_score=failure_hint_score,
        ranker_score=ranker_score,
    )
