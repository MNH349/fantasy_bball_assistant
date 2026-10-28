import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fba import names  # noqa: E402


def test_normalize_strips_accents_suffixes_punct():
    assert names.normalize("Nikola Jokić") == "nikola jokic"
    assert names.normalize("Jimmy Butler III") == "jimmy butler"
    assert names.normalize("A.J. Green") == "aj green"
    assert names.normalize("Shai Gilgeous-Alexander") == "shai gilgeous alexander"


def test_matcher_exact():
    m = names.Matcher({"nikola jokic": "hit"})
    assert m.get("Nikola Jokić") == "hit"
    assert m.get("LeBron James") is None


def test_matcher_fuzzy_nickname():
    # "Alexandre Sarr" should resolve to an index keyed by "Alex Sarr".
    m = names.Matcher({"alex sarr": "sarr"})
    assert m.get("Alexandre Sarr") == "sarr"
    m2 = names.Matcher({"cameron thomas": "cam"})
    assert m2.get("Cam Thomas") == "cam"


def test_matcher_does_not_match_unrelated_same_last():
    # Different first names that aren't prefixes must not collide.
    m = names.Matcher({"jaylen brown": "jb"})
    assert m.get("Jalen Brown") is None  # jaylen vs jalen: neither prefixes? 'jalen' not prefix of 'jaylen'
