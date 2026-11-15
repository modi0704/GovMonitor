"""A small evaluator for the formulas the Excel export writes (MASTERPLAN 9.3, P9.5).

It ignores every cached result and recomputes each formula from the cell inputs, so a test using it
checks the formulas themselves. Supports what the export uses: numbers, strings, cell references
(with or without ``$``, optionally ``'Sheet'!``), ranges, ``+ - * /``, unary minus, parentheses,
``SUM`` and ``SUMIF(range, "text", sum_range)``. Blank cells count as 0.
"""

import re
from decimal import Decimal

import openpyxl
from openpyxl.utils import column_index_from_string, get_column_letter

TOKEN = re.compile(
    r"\s*(?:"
    r"(?P<num>\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)"
    r"|(?P<str>\"[^\"]*\")"
    r"|(?P<range>\$?[A-Z]{1,3}\$?\d+:\$?[A-Z]{1,3}\$?\d+)"
    r"|(?P<ref>\$?[A-Z]{1,3}\$?\d+)"
    r"|(?P<func>[A-Z]+)\("
    r"|(?P<op>[-+*/(),])"
    r")"
)


class FormulaError(Exception):
    pass


def _cell(ref: str) -> tuple[str, int]:
    m = re.fullmatch(r"\$?([A-Z]{1,3})\$?(\d+)", ref)
    return m.group(1), int(m.group(2))


class Evaluator:
    def __init__(self, path_or_file):
        self.wb = openpyxl.load_workbook(path_or_file)  # formulas, not cached values
        self.cache: dict = {}

    def value(self, sheet: str, ref: str):
        col, row = _cell(ref)
        key = (sheet, col, row)
        if key in self.cache:
            return self.cache[key]
        raw = self.wb[sheet][f"{col}{row}"].value
        if isinstance(raw, str) and raw.startswith("="):
            self.cache[key] = None  # cycle guard
            result = self._eval(sheet, raw[1:])
        elif isinstance(raw, (int, float)):
            result = Decimal(str(raw))
        else:
            result = raw
        self.cache[key] = result
        return result

    def number(self, sheet: str, ref: str) -> Decimal:
        v = self.value(sheet, ref)
        return v if isinstance(v, Decimal) else Decimal(0)

    # ---- parser ----
    def _eval(self, sheet: str, text: str):
        tokens = []
        pos = 0
        while pos < len(text):
            m = TOKEN.match(text, pos)
            if not m or m.end() == pos:
                if text[pos:].strip() == "":
                    break
                raise FormulaError(f"cannot parse {text!r} at {pos}")
            kind = m.lastgroup
            tokens.append((kind, m.group(kind)))
            pos = m.end()
        saved = getattr(self, "_tokens", None), getattr(self, "_i", 0), getattr(self, "_sheet", None)
        self._tokens, self._i, self._sheet = tokens, 0, sheet  # references re-enter _eval: save state
        try:
            result = self._expr()
            if self._i != len(tokens):
                raise FormulaError(f"trailing tokens in {text!r}")
            return result
        finally:
            self._tokens, self._i, self._sheet = saved

    def _peek(self):
        return self._tokens[self._i] if self._i < len(self._tokens) else (None, None)

    def _take(self):
        tok = self._peek()
        self._i += 1
        return tok

    def _expr(self):
        left = self._term()
        while self._peek() in (("op", "+"), ("op", "-")):
            op = self._take()[1]
            right = self._term()
            left = _num(left) + _num(right) if op == "+" else _num(left) - _num(right)
        return left

    def _term(self):
        left = self._unary()
        while self._peek() in (("op", "*"), ("op", "/")):
            op = self._take()[1]
            right = self._unary()
            if op == "*":
                left = _num(left) * _num(right)
            else:
                if _num(right) == 0:
                    raise FormulaError("#DIV/0!")
                left = _num(left) / _num(right)
        return left

    def _unary(self):
        if self._peek() == ("op", "-"):
            self._take()
            return -_num(self._unary())
        if self._peek() == ("op", "+"):
            self._take()
            return self._unary()
        return self._atom()

    def _atom(self):
        kind, text = self._take()
        if kind == "num":
            return Decimal(text)
        if kind == "str":
            return text[1:-1]
        if kind == "ref":
            return self.value(self._sheet, text)
        if kind == "range":
            return self._range(text)
        if kind == "func":
            args = []
            if self._peek() != ("op", ")"):
                args.append(self._expr())
                while self._peek() == ("op", ","):
                    self._take()
                    args.append(self._expr())
            if self._take() != ("op", ")"):
                raise FormulaError("missing )")
            return self._call(text, args)
        if (kind, text) == ("op", "("):
            v = self._expr()
            if self._take() != ("op", ")"):
                raise FormulaError("missing )")
            return v
        raise FormulaError(f"unexpected token {text!r}")

    def _range(self, text: str) -> list:
        a, b = text.split(":")
        (c1, r1), (c2, r2) = _cell(a), _cell(b)
        cols = range(column_index_from_string(c1), column_index_from_string(c2) + 1)
        return [
            [self.value(self._sheet, f"{get_column_letter(c)}{r}") for c in cols] for r in range(r1, r2 + 1)
        ]

    def _call(self, name: str, args: list):
        if name == "SUM":
            total = Decimal(0)
            for a in args:
                for v in _flat(a):
                    total += _num(v) if isinstance(v, Decimal) else Decimal(0)
            return total
        if name == "SUMIF":
            crit_range, crit, sum_range = args
            total = Decimal(0)
            for c, s in zip(_flat(crit_range), _flat(sum_range), strict=True):
                if isinstance(c, str) and c.upper() == str(crit).upper() and isinstance(s, Decimal):
                    total += s
            return total
        raise FormulaError(f"unsupported function {name}")


def _flat(v) -> list:
    if isinstance(v, list):
        return [x for row in v for x in (row if isinstance(row, list) else [row])]
    return [v]


def _num(v) -> Decimal:
    if v is None or v == "":
        return Decimal(0)
    if isinstance(v, Decimal):
        return v
    raise FormulaError(f"not a number: {v!r}")
