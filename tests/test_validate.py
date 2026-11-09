from datetime import date

import pytest
from conftest import NOW, default_manifest, repo_row, write_dataset

from hot_repos.validate import validate


def test_valid_dataset_has_no_problems(dataset):
    assert validate(dataset) == []


def test_empty_directory_reports_missing_files(tmp_path):
    problems = validate(tmp_path)
    assert len(problems) == 4
    assert all("文件不存在" in p for p in problems)


def has(problems, text):
    return any(text in p for p in problems)


def test_duplicate_name_ignoring_case(tmp_path):
    repos = [repo_row("a/one", 1, 200), repo_row("A/One", 3, 100)]
    assert has(validate(write_dataset(tmp_path, repos=repos)), "full_name 重复")


def test_duplicate_rank(tmp_path):
    repos = [repo_row("a/one", 1, 200), repo_row("b/two", 1, 100)]
    assert has(validate(write_dataset(tmp_path, repos=repos)), "rank 重复")


def test_negative_count(tmp_path):
    bad = repo_row("b/two", 3, 100) | {"forks": -1}
    repos = [repo_row("a/one", 1, 200), bad]
    assert has(validate(write_dataset(tmp_path, repos=repos)), "forks 为负数")


def test_release_tag_and_time_must_pair(tmp_path):
    bad = repo_row("b/two", 3, 100) | {"latest_release_at": None}
    repos = [repo_row("a/one", 1, 200), bad]
    assert has(validate(write_dataset(tmp_path, repos=repos)), "同时有值或同时为空")


def test_star_weeks_columns_must_be_consistent(tmp_path):
    bad = repo_row("b/two", 3, 100) | {"star_weeks_pages_total": None}
    repos = [repo_row("a/one", 1, 200), bad]
    assert has(validate(write_dataset(tmp_path, repos=repos)), "star_weeks_* 三列")


def test_unknown_readme_filename(tmp_path):
    bad = repo_row("b/two", 3, 100) | {"readme_path": "README.rst"}
    repos = [repo_row("a/one", 1, 200), bad]
    assert has(validate(write_dataset(tmp_path, repos=repos)), "readme_path")


def test_week_not_sunday(tmp_path):
    weeks = [{"full_name": "a/one", "week_start": date(2026, 1, 5), "stars": 7, "days": [1] * 7}]
    assert has(validate(write_dataset(tmp_path, weeks=weeks)), "不是周日")


def test_days_must_sum_to_stars(tmp_path):
    weeks = [{"full_name": "a/one", "week_start": date(2026, 1, 4), "stars": 8, "days": [1] * 7}]
    assert has(validate(write_dataset(tmp_path, weeks=weeks)), "之和")


def test_weeks_for_unknown_repo(tmp_path):
    weeks = [{"full_name": "x/y", "week_start": date(2026, 1, 4), "stars": 0, "days": [0] * 7}]
    assert has(validate(write_dataset(tmp_path, weeks=weeks)), "不在 repos.parquet 中")


def test_weeks_exceed_fetched_pages(tmp_path):
    weeks = [
        {"full_name": "a/one", "week_start": date(2026, 1, 4), "stars": 0, "days": [0] * 7},
        {"full_name": "a/one", "week_start": date(2026, 1, 11), "stars": 0, "days": [0] * 7},
    ]
    manifest = default_manifest(star_weeks_per_page=1)
    assert has(validate(write_dataset(tmp_path, weeks=weeks, manifest=manifest)), "周数超过")


def test_rank_history_not_descending(tmp_path):
    repos = [repo_row("a/one", 1, 100), repo_row("b/two", 3, 200)]
    assert has(validate(write_dataset(tmp_path, repos=repos)), "降序")


def test_latest_snapshot_must_match_repos(tmp_path):
    ranks = [
        {
            "snapshot_date": date(2026, 1, 10),
            "rank": 1,
            "full_name": "a/one",
            "stars": 200,
            "captured_at": NOW,
        },
        {
            "snapshot_date": date(2026, 1, 10),
            "rank": 2,
            "full_name": "b/two",
            "stars": 100,
            "captured_at": NOW,
        },
    ]
    assert has(validate(write_dataset(tmp_path, ranks=ranks)), "名次不一致")


@pytest.mark.parametrize(
    ("change", "text"),
    [
        ({"snapshot_date": "2026-01-09"}, "最新快照"),
        ({"schema_version": 99}, "schema_version"),
        ({"extra": 1}, "未定义的字段"),
        ({"board_size": "3"}, "应为 int"),
        ({"board_size": 1}, "board_size"),
        ({"aliases": {"zzz/zzz": ["zzz/zzz"]}}, "aliases 的键"),
        ({"aliases": {"a/one": ["old/one"]}}, "应包含当前名称"),
        ({"missing": ["a/one"]}, "missing"),
        ({"run_at": "2026-01-10T12:00:00"}, "缺少时区"),
    ],
)
def test_manifest_rules(tmp_path, change, text):
    manifest = default_manifest(**change)
    assert has(validate(write_dataset(tmp_path, manifest=manifest)), text)


def test_weeks_must_be_contiguous(tmp_path):
    weeks = [
        {"full_name": "a/one", "week_start": date(2026, 1, 4), "stars": 0, "days": [0] * 7},
        {"full_name": "a/one", "week_start": date(2026, 1, 18), "stars": 0, "days": [0] * 7},
    ]
    assert has(validate(write_dataset(tmp_path, weeks=weeks)), "不连续")
