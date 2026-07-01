from pathlib import Path

import pytest

from powerpy.loader.workbooks import Workbooks, find_workbooks

ROOT = Path(__file__).resolve().parents[1]
PARAMS = ROOT / "src" / "powerpy" / "param" / "params.xlsx"
pytestmark = pytest.mark.skipif(not PARAMS.exists(), reason="params.xlsx not present")


def test_legacy_single_file_mode():
    wbs = find_workbooks(legacy_params=PARAMS)
    assert wbs.design == PARAMS
    assert wbs.scenario == PARAMS
    assert wbs.is_split is False


def test_explicit_pair_wins(tmp_path):
    d = tmp_path / "design.xlsx"
    s = tmp_path / "scenario.xlsx"
    d.write_bytes(b"x")
    s.write_bytes(b"x")
    wbs = find_workbooks(design=d, scenario=s)
    assert wbs.design == d and wbs.scenario == s
    assert wbs.is_split is True


def test_lone_design_is_legacy_mode(tmp_path):
    d = tmp_path / "design.xlsx"
    d.write_bytes(b"x")
    wbs = find_workbooks(design=d)
    assert wbs.design == d and wbs.scenario == d
    assert wbs.is_split is False


def test_discovers_pair_in_search_dir(tmp_path):
    (tmp_path / "design.xlsx").write_bytes(b"x")
    (tmp_path / "scenario.xlsx").write_bytes(b"x")
    wbs = find_workbooks(search_dirs=(tmp_path,))
    assert wbs.is_split is True
    assert wbs.design == tmp_path / "design.xlsx"
    assert wbs.scenario == tmp_path / "scenario.xlsx"


def test_falls_back_to_params_in_search_dir(tmp_path):
    (tmp_path / "params.xlsx").write_bytes(b"x")
    wbs = find_workbooks(search_dirs=(tmp_path,))
    assert wbs.is_split is False
    assert wbs.design == tmp_path / "params.xlsx"


def test_nothing_found_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        find_workbooks(search_dirs=(tmp_path,))


def test_missing_explicit_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        find_workbooks(design=tmp_path / "nope.xlsx")
