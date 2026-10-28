import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fba import storage  # noqa: E402


def _isolate(tmp_path, monkeypatch):
    """Point the store at a throwaway DB so tests never touch real data."""
    monkeypatch.setattr(storage, "DATA_CACHE_DIR", tmp_path)
    monkeypatch.setattr(storage, "HISTORY_DB", tmp_path / "history.db")


def test_save_and_load_latest(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    storage.save_snapshot([{"name": "A", "value_ros": 100.0}], "2026-10-26")
    storage.save_snapshot([{"name": "A", "value_ros": 120.0}], "2026-10-27")
    assert storage.latest_date() == "2026-10-27"
    snap = storage.load_snapshot()
    assert snap[0]["name"] == "A" and snap[0]["value_ros"] == 120.0


def test_save_is_idempotent_per_day(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    storage.save_snapshot([{"name": "A", "value_ros": 1.0}], "2026-10-27")
    storage.save_snapshot([{"name": "A", "value_ros": 2.0}], "2026-10-27")  # overwrite
    assert len(storage.load_snapshot("2026-10-27")) == 1
    assert storage.load_snapshot("2026-10-27")[0]["value_ros"] == 2.0


def test_player_history_is_oldest_first(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    storage.save_snapshot([{"name": "A", "dpm": 1.0}], "2026-10-26")
    storage.save_snapshot([{"name": "A", "dpm": 2.0}], "2026-10-27")
    hist = storage.player_history("A")
    assert [h["snapshot_date"] for h in hist] == ["2026-10-26", "2026-10-27"]
