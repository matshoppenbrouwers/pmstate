"""Generic multi-source feedback example tree.

Two log leaves (``/web``, ``/chat``) feed a ``feedback_rollup`` reducer at
``/feedback``. Vendor-neutral by design — no product, channel, or org names.
"""
from pathlib import Path

from examples.feedback.reducers import feedback_rollup
from examples.feedback.views import source_view
from pmstate import Log, Node, Tree

_S = Path(__file__).parent / "state"


def build_tree() -> Tree:
    feedback = Node("feedback", description="Multi-source product feedback rollup.",
        reducer=feedback_rollup, children=[
            Node("web", state=Log(_S / "web.jsonl"), view=source_view),
            Node("chat", state=Log(_S / "chat.jsonl"), view=source_view),
        ])
    return Tree("feedback_demo", root=Node("product", children=[feedback]))
