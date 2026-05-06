"""pmstate: the directory tree IS the process state."""

from pmstate._paths import NodePathError
from pmstate.envelope import Event
from pmstate.node import Node
from pmstate.reader import ReaderError, read_events
from pmstate.storage import Log, Table
from pmstate.upcasters import UpcastCycleError, Upcaster, UpcasterRegistry, default_registry
from pmstate.writer import EventTooLargeError, append_event

__version__ = "0.0.1"

__all__ = [
    "Event",
    "EventTooLargeError",
    "Log",
    "Node",
    "NodePathError",
    "ReaderError",
    "Table",
    "UpcastCycleError",
    "Upcaster",
    "UpcasterRegistry",
    "__version__",
    "append_event",
    "default_registry",
    "read_events",
]
