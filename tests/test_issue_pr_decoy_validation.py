from __future__ import annotations

import json
from pathlib import Path

from j3.issue_pr_candidate_attempt import (
    PYTEST_TIMEDELTA_APPROX_REPLAY_ID,
    SCRAPY_DOWNLOADER_AWARE_REPLAY_ID,
)
from j3.issue_pr_decoy_validation import (
    build_pytest_decoy_validation_bundle,
    build_scrapy_decoy_validation_bundle,
    load_issue_pr_decoy_validation_bundle_index,
    main,
    write_issue_pr_decoy_validation_bundle,
)


def test_scrapy_decoy_validation_bundle_materializes_snapshots(tmp_path: Path) -> None:
    repo = _write_synthetic_scrapy_checkout(tmp_path / "scrapy")

    bundle = build_scrapy_decoy_validation_bundle(
        repo,
        out_dir=tmp_path / "out",
        validate=False,
        decoy_ids=["scrapy_stale_min_stats_selection", "scrapy_missing_tests"],
    )

    assert bundle["summary"]["candidate_count"] == 2
    assert bundle["summary"]["candidate_after_available_count"] == 2
    assert bundle["summary"]["validation_status_counts"] == {"not_run": 2}
    candidates = {candidate["decoy_id"]: candidate for candidate in bundle["candidates"]}
    assert candidates["scrapy_stale_min_stats_selection"]["touched_file_paths"] == [
        "tests/test_pqueues.py"
    ]
    assert candidates["scrapy_missing_tests"]["touched_file_paths"] == ["scrapy/pqueues.py"]
    assert candidates["scrapy_missing_tests"]["candidate_after"]["available"] is True
    assert all(
        Path(snapshot["after_snapshot_path"]).is_file()
        for candidate in candidates.values()
        for snapshot in candidate["snapshots"]
    )

    artifacts = write_issue_pr_decoy_validation_bundle(bundle, out_dir=tmp_path / "out")
    assert json.loads(artifacts["bundle_json"].read_text(encoding="utf-8"))[
        "schema_version"
    ]
    assert "DATA-039 Live Issue/PR Decoy Validation" in artifacts[
        "report_md"
    ].read_text(encoding="utf-8")
    index = load_issue_pr_decoy_validation_bundle_index(artifacts["bundle_json"])
    assert (
        f"{SCRAPY_DOWNLOADER_AWARE_REPLAY_ID}:scrapy_missing_tests" in index
    )


def test_decoy_validation_cli_writes_bundle(tmp_path: Path) -> None:
    repo = _write_synthetic_scrapy_checkout(tmp_path / "scrapy")

    exit_code = main(
        [
            "--repo-path",
            str(repo),
            "--out-dir",
            str(tmp_path / "cli-out"),
            "--decoy-id",
            "scrapy_missing_last_selected_slot",
        ]
    )

    assert exit_code == 0
    bundle = json.loads(
        (tmp_path / "cli-out" / "decoy-validation-bundle.json").read_text(
            encoding="utf-8"
        )
    )
    assert bundle["summary"]["candidate_count"] == 1
    assert bundle["candidates"][0]["decoy_id"] == "scrapy_missing_last_selected_slot"


def test_pytest_decoy_validation_bundle_materializes_snapshots(tmp_path: Path) -> None:
    repo = _write_synthetic_pytest_timedelta_approx_checkout(tmp_path / "pytest")

    bundle = build_pytest_decoy_validation_bundle(
        repo,
        out_dir=tmp_path / "pytest-out",
        validate=False,
        decoy_ids=[
            "pytest_missing_container_dispatch",
            "pytest_missing_invalid_tolerance_tests",
        ],
    )

    assert bundle["task_id"] == "DATA-040"
    assert bundle["summary"]["candidate_count"] == 2
    assert bundle["summary"]["candidate_after_available_count"] == 2
    candidates = {candidate["decoy_id"]: candidate for candidate in bundle["candidates"]}
    assert candidates["pytest_missing_container_dispatch"]["touched_file_paths"] == [
        "src/_pytest/python_api.py",
        "testing/python/approx.py",
    ]
    assert candidates["pytest_missing_invalid_tolerance_tests"]["candidate_after"][
        "available"
    ] is True
    assert {
        snapshot["path"]
        for snapshot in candidates["pytest_missing_invalid_tolerance_tests"]["snapshots"]
    } == {"src/_pytest/python_api.py", "testing/python/approx.py"}

    artifacts = write_issue_pr_decoy_validation_bundle(
        bundle,
        out_dir=tmp_path / "pytest-out",
    )
    assert "DATA-040 Live Issue/PR Decoy Validation" in artifacts[
        "report_md"
    ].read_text(encoding="utf-8")
    index = load_issue_pr_decoy_validation_bundle_index(artifacts["bundle_json"])
    assert (
        f"{PYTEST_TIMEDELTA_APPROX_REPLAY_ID}:pytest_missing_container_dispatch"
        in index
    )


def test_decoy_validation_cli_writes_pytest_bundle(tmp_path: Path) -> None:
    repo = _write_synthetic_pytest_timedelta_approx_checkout(tmp_path / "pytest")

    exit_code = main(
        [
            "--repo-path",
            str(repo),
            "--replay-id",
            PYTEST_TIMEDELTA_APPROX_REPLAY_ID,
            "--out-dir",
            str(tmp_path / "pytest-cli-out"),
            "--decoy-id",
            "pytest_partial_source_test_materialization",
        ]
    )

    assert exit_code == 0
    bundle = json.loads(
        (tmp_path / "pytest-cli-out" / "decoy-validation-bundle.json").read_text(
            encoding="utf-8"
        )
    )
    assert bundle["summary"]["replay_id"] == PYTEST_TIMEDELTA_APPROX_REPLAY_ID
    assert bundle["candidates"][0]["decoy_id"] == (
        "pytest_partial_source_test_materialization"
    )


def _write_synthetic_scrapy_checkout(repo: Path) -> Path:
    (repo / "scrapy").mkdir(parents=True)
    (repo / "tests").mkdir(parents=True)
    (repo / "scrapy" / "pqueues.py").write_text(
        """from __future__ import annotations

from typing import Iterable, Self


class Crawler:
    settings = {}
    engine = None


class QueueProtocol:
    pass


class Request:
    def __init__(self, url: str):
        self.url = url
        self.meta = {}


class ScrapyPriorityQueue:
    pass


def _path_safe(slot: str) -> str:
    return slot


class DownloaderInterface:
    def __init__(self, crawler: Crawler):
        self.downloader = crawler.engine.downloader

    def stats(self, possible_slots: Iterable[str]) -> list[tuple[int, str]]:
        return [(0, slot) for slot in possible_slots]

    def get_slot_key(self, request: Request) -> str:
        return str(request.meta.get("slot", "default"))


class DownloaderAwarePriorityQueue:
    @classmethod
    def from_crawler(
        cls,
        crawler: Crawler,
        downstream_queue_cls: type[QueueProtocol],
        key: str,
        startprios: dict[str, Iterable[int]] | None = None,
        *,
        start_queue_cls: type[QueueProtocol] | None = None,
    ) -> Self:
        return cls(
            crawler,
            downstream_queue_cls,
            key,
            startprios,
            start_queue_cls=start_queue_cls,
        )

    def __init__(
        self,
        crawler: Crawler,
        downstream_queue_cls: type[QueueProtocol],
        key: str,
        slot_startprios: dict[str, Iterable[int]] | None = None,
        *,
        start_queue_cls: type[QueueProtocol] | None = None,
    ):
        self._downloader_interface: DownloaderInterface = DownloaderInterface(crawler)
        self.downstream_queue_cls: type[QueueProtocol] = downstream_queue_cls
        self._start_queue_cls: type[QueueProtocol] | None = start_queue_cls
        self.key: str = key
        self.crawler: Crawler = crawler

        self.pqueues: dict[str, ScrapyPriorityQueue] = {}  # slot -> priority queue
        if slot_startprios:
            for slot, startprios in slot_startprios.items():
                self.pqueues[slot] = self.pqfactory(slot, startprios)

    def pqfactory(
        self, slot: str, startprios: Iterable[int] = ()
    ) -> ScrapyPriorityQueue:
        return ScrapyPriorityQueue()

    def pop(self) -> Request | None:
        stats = self._downloader_interface.stats(self.pqueues)

        if not stats:
            return None

        slot = min(stats)[1]
        queue = self.pqueues[slot]
        request = queue.pop()
        if len(queue) == 0:
            del self.pqueues[slot]
        return request

    def push(self, request: Request) -> None:
        slot = self._downloader_interface.get_slot_key(request)
        if slot not in self.pqueues:
            self.pqueues[slot] = self.pqfactory(slot)
        queue = self.pqueues[slot]
        queue.push(request)

    def peek(self) -> Request | None:
        stats = self._downloader_interface.stats(self.pqueues)
        if not stats:
            return None
        slot = min(stats)[1]
        queue = self.pqueues[slot]
        return queue.peek()
""",
        encoding="utf-8",
    )
    (repo / "tests" / "test_pqueues.py").write_text(
        """import queuelib

from scrapy.http.request import Request
from scrapy.pqueues import DownloaderAwarePriorityQueue, ScrapyPriorityQueue


class TestDownloaderAwarePriorityQueue:
    def test_peek(self):
        assert True


@pytest.mark.parametrize(
    ("input_", "output"),
    [
        ([{}, {}], [2, 1]),
    ],
)
def test_pop_order(input_, output):
    assert input_
    assert output
""",
        encoding="utf-8",
    )
    return repo


def _write_synthetic_pytest_timedelta_approx_checkout(repo: Path) -> Path:
    (repo / "src" / "_pytest").mkdir(parents=True)
    (repo / "testing" / "python").mkdir(parents=True)
    (repo / "src" / "_pytest" / "python_api.py").write_text(
        """from __future__ import annotations

import builtins
from collections.abc import Collection
from collections.abc import Mapping
from collections.abc import Sized
from datetime import datetime
from datetime import timedelta
from decimal import Decimal
import math
from typing import Any


class ApproxBase:
    def __init__(self, expected, rel=None, abs=None, nan_ok: bool = False) -> None:
        self.expected = expected
        self.abs = abs
        self.rel = rel
        self.nan_ok = nan_ok

    def _approx_scalar(self, x) -> ApproxScalar:
        if isinstance(x, Decimal):
            return ApproxDecimal(x, rel=self.rel, abs=self.abs, nan_ok=self.nan_ok)
        return ApproxScalar(x, rel=self.rel, abs=self.abs, nan_ok=self.nan_ok)


class ApproxScalar(ApproxBase):
    pass


class ApproxDecimal(ApproxScalar):
    pass


class ApproxTimedelta(ApproxBase):
    \"\"\"Perform approximate comparisons where the expected value is a
    datetime or timedelta.

    Requires an explicit tolerance as a timedelta.
    Relative tolerance is not supported for datetime comparisons.
    \"\"\"

    def __init__(self, expected, rel=None, abs=None, nan_ok: bool = False) -> None:
        if isinstance(expected, datetime) and rel is not None:
            raise TypeError(
                "pytest.approx() does not support relative tolerance for "
                "datetime comparisons. Use abs=timedelta(...) instead."
            )
        if nan_ok:
            raise TypeError(
                "pytest.approx() does not support nan_ok for "
                "datetime/timedelta comparisons."
            )
        if abs is None and rel is None:
            raise TypeError(
                "pytest.approx() requires an explicit tolerance for "
                "datetime/timedelta comparisons: "
                "e.g. approx(expected, abs=timedelta(seconds=1))"
            )
        if abs is not None and not isinstance(abs, timedelta):
            raise TypeError(
                f"absolute tolerance for datetime/timedelta must be a "
                f"timedelta, got {type(abs).__name__}"
            )
        if rel is not None and not isinstance(rel, timedelta):
            raise TypeError(
                f"relative tolerance for timedelta must be a "
                f"timedelta, got {type(rel).__name__}"
            )
        tolerance = max(t for t in (abs, rel) if t is not None)
        super().__init__(expected, rel=None, abs=tolerance, nan_ok=False)

    def __repr__(self) -> str:
        return f"{self.expected} +/- {self.abs}"


def _is_sequence_like(expected: object) -> bool:
    return (
        hasattr(expected, "__getitem__")
        and isinstance(expected, Sized)
        and not isinstance(expected, str | bytes)
    )


def _is_numpy_array(obj: object) -> bool:
    return False


def _as_numpy_array(obj: object) -> object:
    return obj


def approx(
    expected: Any,
    rel: float | Decimal | timedelta | None = None,
    abs: float | Decimal | timedelta | None = None,
    nan_ok: bool = False,
) -> ApproxBase:
    \"\"\"Assert that two numbers are equal to each other within some tolerance.

    **datetime and timedelta**

    You can also use ``approx`` to compare :class:`~datetime.datetime` and
    :class:`~datetime.timedelta` objects by specifying an absolute tolerance
    as a :class:`~datetime.timedelta`::

        >>> from datetime import datetime, timedelta
        >>> dt1 = datetime(2024, 1, 1, 12, 0, 0)
        >>> dt2 = datetime(2024, 1, 1, 12, 0, 0, 500000)
        >>> dt1 == approx(dt2, abs=timedelta(seconds=1))
        True

    Note that ``rel`` is not supported for datetime comparisons,
    and ``abs`` or ``rel`` must be explicitly provided as a ``timedelta`` object.
    \"\"\"
    if isinstance(expected, Decimal):
        cls: type[ApproxBase] = ApproxDecimal
    elif isinstance(expected, Mapping):
        cls = ApproxBase
    elif _is_numpy_array(expected):
        expected = _as_numpy_array(expected)
        cls = ApproxBase
    elif _is_sequence_like(expected):
        cls = ApproxBase
    elif isinstance(expected, Collection) and not isinstance(expected, str | bytes):
        msg = f"pytest.approx() only supports ordered sequences, but got: {expected!r}"
        raise TypeError(msg)
    elif isinstance(expected, (datetime, timedelta)):
        cls = ApproxTimedelta
    else:
        cls = ApproxScalar
    return cls(expected, rel, abs, nan_ok)
""",
        encoding="utf-8",
    )
    (repo / "testing" / "python" / "approx.py").write_text(
        """import pytest
from pytest import approx


class TestApproxDatetime:
    \"\"\"Tests for datetime/timedelta support in approx (issue #8395).\"\"\"

    def test_timedelta_rel_within_tolerance(self):
        from datetime import timedelta

        td1 = timedelta(seconds=100)
        td2 = timedelta(seconds=100.5)
        assert td1 == approx(td2, rel=timedelta(seconds=1))

    def test_timedelta_rel_outside_tolerance(self):
        from datetime import timedelta

        td1 = timedelta(seconds=100)
        td2 = timedelta(seconds=102)
        assert td1 != approx(td2, rel=timedelta(seconds=1))

    def test_datetime_rejects_rel(self):
        from datetime import datetime
        from datetime import timedelta

        with pytest.raises(TypeError, match="does not support relative tolerance"):
            approx(datetime(2024, 1, 1), rel=0.1, abs=timedelta(seconds=1))

        with pytest.raises(TypeError, match="does not support relative tolerance"):
            approx(datetime(2024, 1, 1), rel=timedelta(seconds=1))

    def test_abs_must_be_timedelta(self):
        from datetime import datetime

        with pytest.raises(TypeError, match="must be a timedelta"):
            approx(datetime(2024, 1, 1), abs=1.0)

    def test_timedelta_rel_must_be_timedelta(self):
        from datetime import timedelta

        with pytest.raises(TypeError, match="must be a timedelta"):
            approx(timedelta(seconds=1), rel=0.1)

    def test_rejects_nan_ok(self):
        from datetime import datetime
        from datetime import timedelta

        with pytest.raises(TypeError, match="does not support nan_ok"):
            approx(datetime(2024, 1, 1), abs=timedelta(seconds=1), nan_ok=True)

    def test_repr_compare_with_incompatible_type(self):
        result = ["comparison failed", "Obtained: x", "Expected: y", "N/A"]
        assert "comparison failed" in result[0]
        assert "N/A" in result[3]


class MyVec3:
    pass
""",
        encoding="utf-8",
    )
    return repo
