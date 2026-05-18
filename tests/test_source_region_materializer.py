from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

import pytest

from j3.source_region_materializer import (
    SourceRegionAction,
    SourceRegionActionKind,
    SourceRegionConstraints,
    SourceRegionMaterializationError,
    SourceRegionTarget,
    materialize_source_region,
)


REQUESTS_UTILS_PATH = "src/requests/utils.py"


def test_source_region_action_serializes_requests_probe_contract(
    tmp_path: Path,
) -> None:
    source_path = _write_requests_utils_fixture(tmp_path)
    action = _requests_domain_boundary_action(source_path.read_text(encoding="utf-8"))

    record = action.to_record()

    assert json.loads(json.dumps(record, sort_keys=True)) == record
    assert record["schema_version"] == "source-region-action-v1"
    assert record["kind"] == "replace_function_region"
    assert record["target"] == {
        "file_path": REQUESTS_UTILS_PATH,
        "function_name": "should_bypass_proxies",
        "region_name": "no_proxy_host_matching_loop",
        "start_line": action.target.start_line,
        "end_line": action.target.end_line,
        "start_marker": None,
        "end_marker": None,
    }
    assert record["constraints"] == {
        "max_changed_source_lines": 12,
        "must_parse_ast": True,
        "must_preserve_signature": True,
        "allowed_import_changes": [],
    }


def test_materializes_requests_domain_boundary_region_with_metadata(
    tmp_path: Path,
) -> None:
    source_path = _write_requests_utils_fixture(tmp_path)
    action = _requests_domain_boundary_action(source_path.read_text(encoding="utf-8"))

    result = materialize_source_region(tmp_path, action, write=True)
    record = result.to_record()

    assert json.loads(json.dumps(record, sort_keys=True)) == record
    assert result.status == "materialized"
    assert result.target_function == "should_bypass_proxies"
    assert result.touched_region == {
        "start_line": action.target.start_line,
        "end_line": action.target.end_line,
        "region_name": "no_proxy_host_matching_loop",
        "selector": "line_range",
    }
    assert result.changed_line_count == 6
    assert result.added_line_count == 5
    assert result.removed_line_count == 1
    assert result.diff_summary == {
        "hunk_count": 1,
        "changed_line_count": 6,
        "added_line_count": 5,
        "removed_line_count": 1,
    }
    assert result.import_changes == {"added": [], "removed": []}
    assert result.signature_preserved is True
    assert result.ast_parse_ok is True
    assert record["candidate_after"]["ast_delta"]["ast_parse_ok"] is True  # type: ignore[index]
    assert "-        if host.endswith(hostname) or host_with_port.endswith(hostname):" in result.diff
    assert '+        if host == normalized or host.endswith("." + normalized):' in result.diff
    assert source_path.read_text(encoding="utf-8") == result.patched_source

    namespace: dict[str, object] = {}
    exec(result.patched_source, namespace)
    should_bypass_proxies = namespace["should_bypass_proxies"]

    assert should_bypass_proxies("https://notexample.com", "example.com") is False
    assert should_bypass_proxies("https://api.example.com", "example.com") is True
    assert should_bypass_proxies("https://example.com:443", "example.com:443") is True
    assert should_bypass_proxies("https://example.com:444", "example.com:443") is False


def test_source_region_materializer_rejects_invalid_python_after_replacement(
    tmp_path: Path,
) -> None:
    source_path = _write_requests_utils_fixture(tmp_path)
    action = _requests_domain_boundary_action(
        source_path.read_text(encoding="utf-8"),
        replacement_source="        if host == hostname\n            return True\n",
    )

    with pytest.raises(SourceRegionMaterializationError, match="invalid Python") as exc:
        materialize_source_region(tmp_path, action)

    assert exc.value.residual == "source_region_synthesis"


def test_source_region_materializer_preserves_target_function_signature(
    tmp_path: Path,
) -> None:
    source_path = _write_requests_utils_fixture(tmp_path)
    source = source_path.read_text(encoding="utf-8")
    def_line = _line_number(source, "def should_bypass_proxies(url, no_proxy):")
    action = SourceRegionAction(
        kind=SourceRegionActionKind.REPLACE_FUNCTION_REGION,
        target=SourceRegionTarget(
            file_path=REQUESTS_UTILS_PATH,
            function_name="should_bypass_proxies",
            region_name="function_signature",
            start_line=def_line,
            end_line=def_line,
        ),
        replacement_source="def should_bypass_proxies(url, no_proxy=None):\n",
    )

    with pytest.raises(
        SourceRegionMaterializationError,
        match="target function signature changed",
    ) as exc:
        materialize_source_region(tmp_path, action)

    assert exc.value.residual == "validation"


def test_source_region_materializer_enforces_changed_line_budget(
    tmp_path: Path,
) -> None:
    source_path = _write_requests_utils_fixture(tmp_path)
    action = _requests_domain_boundary_action(
        source_path.read_text(encoding="utf-8"),
        constraints=SourceRegionConstraints(max_changed_source_lines=2),
    )

    with pytest.raises(
        SourceRegionMaterializationError,
        match="changed line budget exceeded",
    ) as exc:
        materialize_source_region(tmp_path, action)

    assert exc.value.residual == "validation"


def test_delimited_region_materializer_rejects_import_changes_by_default(
    tmp_path: Path,
) -> None:
    source = dedent(
        """
        # j3:start imports
        import os
        # j3:end imports

        def current_directory():
            return os.getcwd()
        """
    ).lstrip()
    module_path = tmp_path / "module.py"
    module_path.write_text(source, encoding="utf-8")
    action = SourceRegionAction(
        kind=SourceRegionActionKind.REPLACE_DELIMITED_REGION,
        target=SourceRegionTarget(
            file_path="module.py",
            region_name="imports",
            start_marker="# j3:start imports",
            end_marker="# j3:end imports",
        ),
        replacement_source="import sys\n",
    )

    with pytest.raises(
        SourceRegionMaterializationError,
        match="import changes are not allowed",
    ) as exc:
        materialize_source_region(tmp_path, action)

    assert exc.value.residual == "validation"


def _write_requests_utils_fixture(repo: Path) -> Path:
    source_path = repo / REQUESTS_UTILS_PATH
    source_path.parent.mkdir(parents=True)
    source_path.write_text(_requests_utils_source(), encoding="utf-8")
    return source_path


def _requests_domain_boundary_action(
    source: str,
    *,
    replacement_source: str | None = None,
    constraints: SourceRegionConstraints | None = None,
) -> SourceRegionAction:
    target_line = _line_number(
        source,
        "        if host.endswith(hostname) or host_with_port.endswith(hostname):",
    )
    return SourceRegionAction(
        kind=SourceRegionActionKind.REPLACE_FUNCTION_REGION,
        target=SourceRegionTarget(
            file_path=REQUESTS_UTILS_PATH,
            function_name="should_bypass_proxies",
            region_name="no_proxy_host_matching_loop",
            start_line=target_line,
            end_line=target_line,
        ),
        replacement_source=replacement_source or _domain_boundary_replacement(),
        constraints=constraints or SourceRegionConstraints(),
        rationale="requests#7427-shaped no_proxy domain boundary fix",
    )


def _line_number(source: str, needle: str) -> int:
    for index, line in enumerate(source.splitlines(), start=1):
        if line == needle:
            return index
    raise AssertionError(f"line not found: {needle}")


def _requests_utils_source() -> str:
    return dedent(
        """
        from urllib.parse import urlparse


        def should_bypass_proxies(url, no_proxy):
            parsed = urlparse(url)
            host = parsed.hostname
            if not host or not no_proxy:
                return False
            port = parsed.port
            host_with_port = f"{host}:{port}" if port else host
            for hostname in no_proxy.split(","):
                hostname = hostname.strip()
                if not hostname:
                    continue
                if host.endswith(hostname) or host_with_port.endswith(hostname):
                    return True
            return False
        """
    ).lstrip()


def _domain_boundary_replacement() -> str:
    return "\n".join(
        [
            '        normalized = hostname.lstrip(".")',
            '        if host == normalized or host.endswith("." + normalized):',
            "            return True",
            "        if host_with_port == normalized:",
            "            return True",
            "",
        ]
    )
