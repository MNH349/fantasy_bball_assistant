"""Player-name normalization for joining across DARKO, ESPN, and FantasyPros.

None of these sources share a player id, so names are the join key — and they
disagree on diacritics ("Jokić" vs "Jokic"), suffixes ("Jimmy Butler III"),
punctuation ("A.J." vs "AJ"), and casing. `normalize()` collapses those so the
same player matches across sources.
"""
from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from typing import Generic, TypeVar

_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}


def normalize(name: str) -> str:
    """Return a canonical key for a player name.

    Strips accents, lowercases, drops punctuation and generational suffixes, and
    collapses whitespace. "Nikola Jokić" and "Nikola Jokic" -> "nikola jokic";
    "Jimmy Butler III" -> "jimmy butler".
    """
    if not name:
        return ""
    # Decompose accents and drop the combining marks (é -> e).
    decomposed = unicodedata.normalize("NFKD", name)
    ascii_name = "".join(c for c in decomposed if not unicodedata.combining(c))
    ascii_name = ascii_name.lower()
    # Periods/apostrophes vanish so initials collapse ("a.j." -> "aj",
    # "o'neal" -> "oneal"); hyphens become spaces ("gilgeous-alexander").
    ascii_name = re.sub(r"[.'`]", "", ascii_name)
    ascii_name = re.sub(r"-", " ", ascii_name)
    ascii_name = re.sub(r"[^a-z0-9 ]", "", ascii_name)
    tokens = [t for t in ascii_name.split() if t and t not in _SUFFIXES]
    return " ".join(tokens)


T = TypeVar("T")


class Matcher(Generic[T]):
    """Resolve a raw player name to a payload across naming differences.

    Exact normalized match first; then a fuzzy fallback keyed on the last name
    with a first-name prefix test, so "Alexandre Sarr" finds "Alex Sarr" and
    "Cam Thomas" finds "Cameron Thomas" without risking unrelated players.
    """

    def __init__(self, mapping: dict[str, T]):
        self.mapping = mapping
        self.by_last: dict[str, list[tuple[str, T]]] = defaultdict(list)
        for key, payload in mapping.items():
            toks = key.split()
            if toks:
                self.by_last[toks[-1]].append((key, payload))

    def get(self, name: str) -> T | None:
        query = normalize(name)
        if query in self.mapping:
            return self.mapping[query]
        toks = query.split()
        if len(toks) < 2:
            return None
        first, last = toks[0], toks[-1]
        for key, payload in self.by_last.get(last, []):
            kt = key.split()
            if len(kt) < 2:
                continue
            kfirst = kt[0]
            if len(first) >= 3 and (kfirst.startswith(first) or first.startswith(kfirst)):
                return payload
        return None
