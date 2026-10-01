"""
baseline.py — the router currently running in production (simplified).

This is a faithful reduction of our live tool-selection code. The scoring
logic, the minimum-score gate and the verb boost are exactly what runs today.
Removed for this exercise: tenant scoping, SQL templates, parameter
extraction, logging, and the module_hint filter.

Read this carefully before you change anything. Several of its behaviours
look like bugs and are not, and at least one looks fine and is not.

Usage:
    python baseline.py "how many purchase orders are pending"
    python baseline.py --all          # route every query in queries.txt
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Optional

HERE = Path(__file__).parent

# Minimum keyword score required to select a tool at all.
# A single generic word ("po", "stock", "tasks") scores 1 and is never enough;
# this deliberately forces thin matches through to a slower fallback layer.
MIN_SCORE = 2

# A verb that signals the desired OUTPUT SHAPE outweighs incidental keyword
# overlap: "list/show/which" wants rows, "how many/count" wants a number.
VERB_BOOST = 2

with (HERE / "tools.json").open() as fh:
    TOOL_REGISTRY: dict[str, dict[str, Any]] = json.load(fh)


def _kw_pattern(kw: str) -> str:
    """Word-boundary, plural-tolerant pattern for a keyword phrase.

    "purchase order" matches "purchase orders"; "po id" matches "po ids".
    Because of the word boundaries, "po" can never match inside "report"
    or "deposit".
    """
    return r"\b" + r"\s+".join(
        re.escape(w) + r"s?" for w in kw.lower().split()
    ) + r"\b"


def _kw_score(tool: dict, q: str) -> int:
    """Sum of word-counts of every keyword phrase found in the query.

    Multi-word phrases are worth more than single words, so
    "purchase order" (2) outranks "po" (1).
    """
    return sum(
        len(kw.split())
        for kw in tool.get("keywords", [])
        if re.search(_kw_pattern(kw), q)
    )


def select_tool(query: str) -> Optional[tuple[dict[str, Any], int]]:
    """Score every tool against the query and return the best match.

    Returns (tool, score) when score >= MIN_SCORE, else None.
    """
    q = query.lower()

    wants_rows = bool(
        re.search(r"\b(list|show|display|see|which|ids?|details)\b|\b(give|get)\s+me\b", q)
    )
    wants_count = bool(
        re.search(r"\b(how many|count|number of|total number)\b", q)
    )

    best_tool: Optional[dict] = None
    best_score: int = 0

    for tool in TOOL_REGISTRY.values():
        score = _kw_score(tool, q)
        if score > 0:  # the verb boost only refines a real keyword match
            out = tool.get("output_type")
            if wants_rows and out == "list":
                score += VERB_BOOST
            if wants_count and out in ("count", "scalar"):
                score += VERB_BOOST
        if score > best_score:
            best_score = score
            best_tool = tool

    if best_tool and best_score >= MIN_SCORE:
        return best_tool, best_score
    return None


def route(query: str) -> tuple[Optional[str], int]:
    """Convenience wrapper: returns (tool_id_or_None, score)."""
    hit = select_tool(query)
    return (hit[0]["id"], hit[1]) if hit else (None, 0)


def _load_queries() -> list[tuple[str, str]]:
    out = []
    for line in (HERE / "queries.txt").read_text().splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        qid, _, text = line.partition("\t")
        out.append((qid.strip(), text.strip()))
    return out


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "--all":
        rows = _load_queries()
        unmatched = 0
        for qid, text in rows:
            tool_id, score = route(text)
            if tool_id is None:
                unmatched += 1
            print(f"{qid}\t{tool_id or '<no match>':<38}\t{score}\t{text}")
        print(
            f"\n{len(rows)} queries · {len(rows) - unmatched} routed · "
            f"{unmatched} fell through to the fallback layer",
            file=sys.stderr,
        )
        return

    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    query = " ".join(sys.argv[1:])
    hit = select_tool(query)
    if hit is None:
        print(f"<no match>  (best score below MIN_SCORE={MIN_SCORE})")
        return
    tool, score = hit
    print(f"tool   : {tool['id']}")
    print(f"score  : {score}")
    print(f"module : {tool['module']}")
    print(f"output : {tool['output_type']}")
    print(f"desc   : {tool['description']}")


if __name__ == "__main__":
    main()
