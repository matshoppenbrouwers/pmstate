"""pmstate: the directory tree IS the process state."""

from typing import TYPE_CHECKING

from pmstate._paths import NodePathError
from pmstate.agents_md import load_agents_md
from pmstate.backends import Cursor, FilesystemBackend, StorageBackend, StorageError
from pmstate.envelope import Event
from pmstate.node import Node
from pmstate.reader import ReaderError, read_events
from pmstate.rollup import compute_view, compute_view_at
from pmstate.storage import Log, Table
from pmstate.tools import ToolError, find_state, get_state, list_tree, read_log
from pmstate.tree import Tree
from pmstate.upcasters import UpcastCycleError, Upcaster, UpcasterRegistry, default_registry
from pmstate.writer import EventTooLargeError, append_event

if TYPE_CHECKING:
    from pmstate.adapters.claude_sdk import Harness as ClaudeHarness


def __getattr__(name: str) -> object:
    if name == "ClaudeHarness":
        try:
            from pmstate.adapters.claude_sdk import Harness as _Harness  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError(
                "ClaudeHarness requires the claude-sdk extra: "
                "pip install pmstate[claude-sdk]"
            ) from exc
        return _Harness
    raise AttributeError(f"module 'pmstate' has no attribute {name!r}")


__version__ = "0.4.0"

__all__ = [
    "ClaudeHarness",
    "Cursor",
    "Event",
    "EventTooLargeError",
    "FilesystemBackend",
    "Log",
    "Node",
    "NodePathError",
    "ReaderError",
    "StorageBackend",
    "StorageError",
    "Table",
    "ToolError",
    "Tree",
    "UpcastCycleError",
    "Upcaster",
    "UpcasterRegistry",
    "__version__",
    "append_event",
    "compute_view",
    "compute_view_at",
    "default_registry",
    "find_state",
    "get_state",
    "list_tree",
    "load_agents_md",
    "read_events",
    "read_log",
]
