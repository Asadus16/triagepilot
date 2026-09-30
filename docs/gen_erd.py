"""Generates docs/erd-real.html from the real schema in app/store.py, the same
"auto-generated from the live schema, not hand-drawn" principle the sibling projects
(claim-triage-agent, analytics-agent) use. Parses the actual CREATE TABLE statements,
so the diagram can't drift from the real database.

Usage: python3 docs/gen_erd.py   (writes docs/erd-real.html)
Then screenshot it with the project's own screenshot.mjs to get erd-real.png.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.store import _SCHEMA  # the single source of truth for the schema

TABLE_RE = re.compile(r"CREATE TABLE IF NOT EXISTS (\w+) \((.*?)\);", re.DOTALL)
COL_RE = re.compile(r"^\s*(\w+)\s+([A-Z]+)(.*)$")


def parse_schema(sql: str) -> list[dict]:
    tables = []
    for name, body in TABLE_RE.findall(sql):
        columns = []
        fks = []
        for raw_line in body.split(",\n"):
            line = raw_line.strip().rstrip(",")
            if not line:
                continue
            ref = re.search(r"REFERENCES (\w+)\((\w+)\)", line)
            if ref:
                col_match = COL_RE.match(line)
                if col_match:
                    fks.append({"column": col_match.group(1), "to_table": ref.group(1), "to_column": ref.group(2)})
            col_match = COL_RE.match(line)
            if col_match:
                col_name, col_type, rest = col_match.groups()
                columns.append(
                    {
                        "name": col_name,
                        "type": col_type,
                        "pk": "PRIMARY KEY" in rest,
                        "fk": bool(ref),
                    }
                )
        tables.append({"name": name, "columns": columns, "fks": fks})
    return tables


CARD_POSITIONS = {
    "tickets": (40, 120),
    "decisions": (420, 120),
    "rule_results": (800, 120),
    "human_reviews": (800, 480),
}


def render_html(tables: list[dict]) -> str:
    total_cols = sum(len(t["columns"]) for t in tables)
    cards = []
    for t in tables:
        x, y = CARD_POSITIONS.get(t["name"], (40, 60))
        rows = "".join(
            f'<div class="row"><span class="badge {"pk" if c["pk"] else "fk" if c["fk"] else ""}">'
            f'{"PK" if c["pk"] else "FK" if c["fk"] else ""}</span>'
            f'<span class="col-name">{c["name"]}</span><span class="col-type">{c["type"].lower()}</span></div>'
            for c in t["columns"]
        )
        cards.append(f'<div class="table-card" id="tbl-{t["name"]}" style="left:{x}px;top:{y}px">'
                      f'<div class="table-header">{t["name"]}</div>{rows}</div>')

    lines = []
    for t in tables:
        tx, ty = CARD_POSITIONS.get(t["name"], (40, 60))
        for fk in t["fks"]:
            fx, fy = CARD_POSITIONS.get(fk["to_table"], (40, 60))
            x1, y1 = tx + 10, ty + 34
            x2, y2 = fx + 10, fy + 34
            lines.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#c2410c" stroke-width="2" stroke-dasharray="4 3" marker-end="url(#arrow)"/>')

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
  body {{ margin:0; width:1600px; height:900px; background:#fffaf5; font-family: -apple-system, 'Segoe UI', sans-serif; }}
  .title {{ position:absolute; left:40px; top:16px; font-size:28px; font-weight:800; color:#1c1917; }}
  .title span {{ color:#c2410c; }}
  .subtitle {{ position:absolute; left:40px; top:56px; font-size:14px; color:#78716c; }}
  .table-card {{ position:absolute; width:340px; border:1px solid #e7e5e4; border-radius:10px; background:#fff;
    box-shadow:0 1px 3px rgba(0,0,0,.06); overflow:hidden; }}
  .table-header {{ background:#c2410c; color:#fff; font-weight:700; font-size:15px; padding:10px 14px; }}
  .row {{ display:flex; align-items:center; gap:10px; padding:6px 14px; font-size:13px; border-top:1px solid #f5f5f4; }}
  .badge {{ width:22px; font-size:10px; font-weight:800; color:#a8a29e; }}
  .badge.pk {{ color:#c2410c; }}
  .badge.fk {{ color:#0369a1; }}
  .col-name {{ flex:1; color:#292524; }}
  .col-type {{ color:#a8a29e; font-family: ui-monospace, monospace; font-size:11px; }}
  svg {{ position:absolute; left:0; top:0; }}
</style></head>
<body>
  <div class="title">TriagePilot <span>&mdash; database schema</span></div>
  <div class="subtitle">Auto-generated from the live schema (app/store.py) &middot; {len(tables)} tables &middot; {total_cols} columns</div>
  <svg width="1600" height="900"><defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="#c2410c"/></marker></defs>{''.join(lines)}</svg>
  {''.join(cards)}
</body></html>"""


def main() -> None:
    tables = parse_schema(_SCHEMA)
    out = Path(__file__).resolve().parent / "erd-real.html"
    out.write_text(render_html(tables))
    print(f"wrote {out} ({len(tables)} tables)")


if __name__ == "__main__":
    main()
