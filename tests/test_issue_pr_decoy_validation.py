from __future__ import annotations

import json
from pathlib import Path

from j3.issue_pr_candidate_attempt import SCRAPY_DOWNLOADER_AWARE_REPLAY_ID
from j3.issue_pr_decoy_validation import (
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
