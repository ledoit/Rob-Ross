import json
from pathlib import Path

from core.user_loop import (
    ensure_user_loop_state,
    pick_weighted_ide_moods,
    precompute_ide_taste_moods,
)


def test_pick_weighted_respects_weights():
    import random

    rng = random.Random(42)
    moods = ["a", "b", "c"]
    w = {"a": 0.1, "b": 5.0, "c": 1.0}
    picks = pick_weighted_ide_moods(moods, w, 40, rng)
    assert len(picks) == 40
    assert picks.count("b") > picks.count("a")


def test_precompute_disabled_returns_none():
    import random

    g = {"taste_contexts": {"ide": ["x", "y"]}, "user_loop_state": {"use_weighted_taste_moods": False}}
    assert precompute_ide_taste_moods(g, 3, random.Random(1)) is None


def test_precompute_returns_list(tmp_path: Path):
    import random

    g = {
        "taste_contexts": {"ide": ["m1", "m2", "m3"]},
        "user_loop_state": {"use_weighted_taste_moods": True, "mood_weights": {"m1": 1.0, "m2": 1.0, "m3": 1.0}},
    }
    out = precompute_ide_taste_moods(g, 5, random.Random(99))
    assert out is not None
    assert len(out) == 5


def test_ensure_creates_file(tmp_path: Path):
    genome = {"taste_contexts": {"ide": ["a", "b"]}}
    p = tmp_path / "user_loop_state.json"
    d = ensure_user_loop_state(p, genome)
    assert p.is_file()
    assert d["mood_weights"]["a"] == 1.0
    roundtrip = json.loads(p.read_text(encoding="utf-8"))
    assert roundtrip["version"] == 1
