"""Tree order: siblings by sort order, then name — the order offices are listed everywhere (D27)."""


def tree_key(office, by_id: dict) -> tuple:
    """Sort key placing ``office`` in tree order. ``by_id`` maps office ids (UUID or str) to offices;
    ancestors missing from it fall back to their position in the path."""
    chain = []
    for part in office.path.strip("/").split("/"):
        node = by_id.get(part) or by_id.get(_uuid(part))
        chain.append((node.sort_order, node.name.lower(), part) if node else (0, "", part))
    return tuple(chain)


def _uuid(text):
    import uuid

    try:
        return uuid.UUID(text)
    except ValueError:
        return None
