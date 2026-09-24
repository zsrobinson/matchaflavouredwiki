"""Small helpers for Minecraft's data formats, kept out of extract.py so they can be tested."""


def pack_format(v):
    """A pack.mcmeta min_format or max_format as (major, minor). Minecraft takes a number (88) or
    [major, minor] ([107, 1]); the pack writes [107.1], meaning 107.1. None stays None."""
    if v is None:
        return None
    if isinstance(v, list):
        return (int(v[0]), int(v[1])) if len(v) > 1 else pack_format(v[0])
    return (int(v), round((v - int(v)) * 10))
