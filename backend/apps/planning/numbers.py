from decimal import Decimal


def plain(value: Decimal | None) -> str | None:
    """A decimal without trailing zeros and never in exponent form: 10.0000 -> "10", 2.50 -> "2.5"."""
    if value is None:
        return None
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"
