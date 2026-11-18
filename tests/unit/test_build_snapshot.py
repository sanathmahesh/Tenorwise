"""Phase 0 build step: writes the same JSON to the web folder and the function folder.

At this stage the snapshot holds only meta.json (no market data yet) and
build_check.json, which proves numpy and scipy ran at build time.
"""

import json

from tenorwise.snapshot.build import build_snapshot

META_FIELDS = {"data_date", "build_time", "git_sha", "fred_series", "llm_model", "assumptions"}


def _build(tmp_path, name):
    web_dir = tmp_path / name / "web"
    fn_dir = tmp_path / name / "function"
    build_snapshot(
        out_dirs=[web_dir, fn_dir],
        build_time="2000-01-04T12:00:00Z",
        git_sha="abc1234",
        llm_model="test-org/test-model",
    )
    return web_dir, fn_dir


def test_writes_identical_files_to_every_output_dir(tmp_path):
    web_dir, fn_dir = _build(tmp_path, "a")

    for name in ("meta.json", "build_check.json"):
        assert (web_dir / name).read_bytes() == (fn_dir / name).read_bytes()


def test_meta_has_contract_fields_and_no_market_data_yet(tmp_path):
    web_dir, _ = _build(tmp_path, "a")

    meta = json.loads((web_dir / "meta.json").read_text())

    assert set(meta) == META_FIELDS
    assert meta["data_date"] is None
    assert meta["fred_series"] == []
    assert meta["git_sha"] == "abc1234"
    assert meta["llm_model"] == "test-org/test-model"


def test_build_check_shows_numpy_and_scipy_ran(tmp_path):
    web_dir, _ = _build(tmp_path, "a")

    check = json.loads((web_dir / "build_check.json").read_text())

    assert check["numpy_version"]
    assert check["scipy_version"]
    assert check["python_version"].startswith("3.12")
    assert abs(check["brentq_sqrt2"] - 2**0.5) < 1e-12


def test_same_inputs_give_byte_identical_output(tmp_path):
    first, _ = _build(tmp_path, "a")
    second, _ = _build(tmp_path, "b")

    for name in ("meta.json", "build_check.json"):
        assert (first / name).read_bytes() == (second / name).read_bytes()
