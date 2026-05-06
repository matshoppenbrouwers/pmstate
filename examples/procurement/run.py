"""End-to-end procurement runner against a real Claude Agent SDK session.

WARNING: invokes the real Claude API. Requires ``ANTHROPIC_API_KEY`` set in the
environment. Costs money per run.

Usage::

    python examples/procurement/run.py "what is pending in procurement?"

Or interactive (no prompt argument)::

    python examples/procurement/run.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from examples.procurement.tree import build_tree
from pmstate import ClaudeHarness

ROOT_DIR = Path(__file__).parent


def main() -> None:
    prompt = sys.argv[1] if len(sys.argv) > 1 else None
    tree = build_tree()
    harness = ClaudeHarness(tree=tree, root_dir=ROOT_DIR, watch=False)
    result = harness.run(prompt)
    if result is not None:
        print(result)


if __name__ == "__main__":
    main()
