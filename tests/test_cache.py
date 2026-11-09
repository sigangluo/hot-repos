from datetime import UTC, datetime, timedelta

from hot_repos import cache
from hot_repos.cache import Fetched, Journal

T0 = datetime(2026, 1, 1, tzinfo=UTC)


def test_fetched_freshness():
    f = Fetched("v", T0)
    assert f.is_fresh(timedelta(hours=1), T0 + timedelta(minutes=59))
    assert not f.is_fresh(timedelta(hours=1), T0 + timedelta(hours=2))
    assert not f.is_fresh(timedelta(0), T0 + timedelta(seconds=1))


def test_stamped_round_trip(tmp_path):
    path = tmp_path / "a.json"
    assert cache.load_stamped(path) is None
    cache.save_stamped(path, {"x": [1, 2]}, T0)
    assert cache.load_stamped(path) == Fetched({"x": [1, 2]}, T0)
    assert not list(tmp_path.glob("*.tmp"))


def test_journal_last_record_wins_and_null_values_are_kept(tmp_path):
    j = Journal(tmp_path / "j.jsonl")
    j.append({"a": 1, "b": None}, T0)
    j.append({"a": 2}, T0 + timedelta(hours=1))
    loaded = j.load()
    assert loaded["a"] == Fetched(2, T0 + timedelta(hours=1))
    assert loaded["b"] == Fetched(None, T0)


def test_journal_recovers_after_interrupted_record(tmp_path):
    path = tmp_path / "j.jsonl"
    j = Journal(path)
    j.append({"a": 1}, T0)
    with path.open("a") as f:
        f.write('{"key":"broken')
    j.append({"b": 2}, T0)
    assert {k: v.value for k, v in j.load().items()} == {"a": 1, "b": 2}


def test_journal_compact_drops_overwritten_records(tmp_path):
    path = tmp_path / "j.jsonl"
    j = Journal(path)
    for i in range(5):
        j.append({"a": i}, T0)
    j.compact()
    assert len(path.read_text().strip().splitlines()) == 1
    assert j.load()["a"].value == 4


def test_journal_compact_with_retention_drops_old_records(tmp_path):
    j = Journal(tmp_path / "j.jsonl")
    j.append({"old": 1}, T0)
    j.append({"new": 2}, T0 + timedelta(days=40))
    j.compact(retention=timedelta(days=30), now=T0 + timedelta(days=41))
    assert list(j.load()) == ["new"]
    j.compact(retention=timedelta(days=30), now=T0 + timedelta(days=200))
    assert not j.path.exists()  # 全部过期时删除文件
