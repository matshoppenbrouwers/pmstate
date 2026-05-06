"""Procurement example tree."""
from pathlib import Path

from examples.procurement.reducers import procurement_rollup
from examples.procurement.views import lpo_view, quote_view
from pmstate import Log, Node, Table, Tree

_S = Path(__file__).parent / "state"


def build_tree() -> Tree:
    procurement = Node("procurement", description="Vendor quotes, LPOs, approvals.",
        reducer=procurement_rollup, children=[
            Node("quotes", state=Log(_S / "quotes.jsonl"), view=quote_view),
            Node("lpos", state=Log(_S / "lpos.jsonl"), view=lpo_view),
            Node("vendors", state=Table(_S / "vendors.json")),
        ])
    return Tree("project_alpha", root=Node("active", children=[procurement]))
