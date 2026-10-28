import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fba import blend  # noqa: E402


def test_weights_by_history_depth():
    assert blend.darko_weight(5) == 0.70   # veteran
    assert blend.darko_weight(1) == 0.30   # sophomore
    assert blend.darko_weight(0) == 0.0    # rookie -> ESPN only


def test_blend_value_weighted_average():
    # vet: 0.7*3000 + 0.3*4000 = 3300
    assert blend.blend_value(3000, 4000, 0.7) == 3300.0
    # sophomore leans ESPN: 0.3*1000 + 0.7*2000 = 1700
    assert blend.blend_value(1000, 2000, 0.3) == 1700.0


def test_rookie_cap_is_downward_only():
    # Market fades him (drafted 40th, ESPN ranks 10th) -> scale by 10/40, then *0.9
    faded = blend.rookie_value(2000, espn_rank=10, adp_rank=40)
    assert faded == round(2000 * (10 / 40) * 0.90, 1)
    # Market likes him more than ESPN -> never boost, just the flat discount.
    liked = blend.rookie_value(2000, espn_rank=40, adp_rank=10)
    assert liked == round(2000 * 0.90, 1)


def test_rookie_discount_applies_without_adp():
    assert blend.rookie_value(2000, espn_rank=None, adp_rank=None) == round(2000 * 0.9, 1)
