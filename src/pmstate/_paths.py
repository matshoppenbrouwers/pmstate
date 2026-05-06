"""Internal path parsing for the node tree. Paths are POSIX-shaped: ``/a/b/c``."""

from __future__ import annotations


class NodePathError(ValueError):
    """Raised when a node path cannot be parsed or doesn't resolve."""

    def __init__(self, path: str, reason: str) -> None:
        super().__init__(f"invalid node path {path!r}: {reason}")
        self.path = path
        self.reason = reason


def parse(path: str) -> tuple[str, ...]:
    """Parse ``/a/b/c`` into ``("a", "b", "c")``. Empty or ``/`` yields ``()``."""
    if not isinstance(path, str):
        raise NodePathError(repr(path), "path must be a string")
    if path in {"", "/"}:
        return ()
    if not path.startswith("/"):
        raise NodePathError(path, "must start with '/'")
    parts = tuple(path[1:].split("/"))
    for segment in parts:
        if not segment:
            raise NodePathError(path, "empty segment (consecutive '/')")
        if segment != segment.strip():
            raise NodePathError(path, f"segment {segment!r} has leading/trailing whitespace")
    return parts


def format(parts: tuple[str, ...]) -> str:
    """Format ``("a", "b")`` back into ``"/a/b"``. Empty tuple yields ``"/"``."""
    if not parts:
        return "/"
    return "/" + "/".join(parts)
