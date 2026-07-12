"""Neutral text-matching layer for catalog retrieval.

Lives in ``catalog/`` so both the web intent layer and the assembly
grounding can use it WITHOUT a catalog -> web dependency. web/intent.py
still carries its private copy until the previews work merges (then it
switches here in a dedicated commit).
"""

from __future__ import annotations

import re

_WORD = re.compile(r"[a-zA-Zа-яА-Я0-9_]+")

#: RU/EN hints mapped onto catalog tokens — keeps deterministic retrieval
#: useful for the Russian-speaking maker without any model.
SYNONYMS = {
    "клипса": "clip", "кабель": "cable", "кабеля": "cable", "провод": "cable",
    "пучок": "bundle", "пучка": "bundle", "стол": "desk", "столом": "desk",
    "коробка": "enclosure box", "корпус": "enclosure box", "крышка": "lid",
    "лампа": "lamp", "лампы": "lamp", "патрон": "socket",
    "кронштейн": "bracket", "крючок": "hook", "крюк": "hook",
    "подставка": "stand", "телефон": "phone", "труба": "pipe",
    "трубы": "pipe", "швабра": "broom", "ручка": "handle", "полка": "shelf",
    "полки": "shelf", "гребенка": "comb", "гребёнка": "comb",
    "стяжка": "zip tie", "канал": "raceway channel", "подшипник": "bearing",
    "ферма": "truss", "распаечная": "junction", "переходник": "adapter",
    "пластина": "plate", "площадка": "plate adapter", "винт": "screw",
    "саморез": "screw", "перфопанель": "pegboard", "перфопанели": "pegboard",
    "слайдер": "rail slider", "защелка": "snap", "защёлка": "snap",
    "защелках": "snap", "защёлках": "snap", "контроллер": "controller pcb",
    "стержень": "rod", "обжим": "clamp", "хвост": "dovetail",
    "ласточкин": "dovetail",
}


def _synonym(word: str) -> str | None:
    """Dictionary lookup with naive RU case-ending stripping — «кронштейне»,
    «патрону», «корпусом» must hit the same entry as the nominative."""
    if word in SYNONYMS:
        return SYNONYMS[word]
    for cut in (1, 2, 3):
        stem = word[:-cut]
        if len(stem) >= 4 and stem in SYNONYMS:
            return SYNONYMS[stem]
    return None


def tokens(text: str) -> list[str]:
    words = [w.lower() for w in _WORD.findall(text)]
    out = []
    for w in words:
        out.append(w)
        mapped = _synonym(w)
        if mapped:
            out.extend(mapped.split())
    return out
