"""Fit text into a box by measuring it (P10.4): long office names are cut with an ellipsis.

Widths are Arial/Helvetica advance widths (per 1000 units of the font size, the standard AFM
metrics), so no font file is needed at run time. Characters not in the table count as wide (600)
and bold text as 8% wider: both err on the side of cutting a little early rather than overflowing.
"""

_WIDTHS = {
    " ": 278, "!": 278, '"': 355, "#": 556, "$": 556, "%": 889, "&": 667, "'": 191, "(": 333, ")": 333,
    "*": 389, "+": 584, ",": 278, "-": 333, ".": 278, "/": 278, ":": 278, ";": 278, "<": 584, "=": 584,
    ">": 584, "?": 556, "@": 1015, "[": 278, "\\": 278, "]": 278, "^": 469, "_": 556, "`": 333,
    "{": 334, "|": 260, "}": 334, "~": 584,
    "A": 667, "B": 667, "C": 722, "D": 722, "E": 667, "F": 611, "G": 778, "H": 722, "I": 278, "J": 500,
    "K": 667, "L": 556, "M": 833, "N": 722, "O": 778, "P": 667, "Q": 778, "R": 722, "S": 667, "T": 611,
    "U": 722, "V": 667, "W": 944, "X": 667, "Y": 667, "Z": 611,
    "a": 556, "b": 556, "c": 500, "d": 556, "e": 556, "f": 278, "g": 556, "h": 556, "i": 222, "j": 222,
    "k": 500, "l": 222, "m": 833, "n": 556, "o": 556, "p": 556, "q": 556, "r": 333, "s": 500, "t": 278,
    "u": 556, "v": 500, "w": 722, "x": 500, "y": 500, "z": 500,
}  # fmt: skip
_WIDTHS.update({str(d): 556 for d in range(10)})
DEFAULT_WIDTH = 600
BOLD_FACTOR = 1.08
ELLIPSIS = "…"


def text_width(text: str, size_pt: float, bold: bool = False) -> float:
    """Width of ``text`` in points at ``size_pt``."""
    units = sum(_WIDTHS.get(ch, DEFAULT_WIDTH) for ch in text)
    return units * size_pt / 1000 * (BOLD_FACTOR if bold else 1)


def fit(text: str, max_width_pt: float, size_pt: float, bold: bool = False) -> str:
    """``text`` unchanged if it fits on one line, else cut at a word (or character) with "…"."""
    text = " ".join(str(text).split())
    if text_width(text, size_pt, bold) <= max_width_pt:
        return text
    budget = max_width_pt - text_width(ELLIPSIS, size_pt, bold)
    cut = ""
    for ch in text:
        if text_width(cut + ch, size_pt, bold) > budget:
            break
        cut += ch
    word_cut = cut.rsplit(" ", 1)[0] if " " in cut and len(cut.rsplit(" ", 1)[0]) >= len(cut) * 0.6 else cut
    return word_cut.rstrip(" ,;:-–") + ELLIPSIS
