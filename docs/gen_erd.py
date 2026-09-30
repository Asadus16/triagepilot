"""Generate a landscape data-model diagram for TriagePilot.

TriagePilot has no relational database -- its store is a single Google Sheet,
configured by one n8n Set node. So this is not a PRAGMA/DDL introspection like
the other projects; it is parsed straight from the two real sources of truth
in this repo: the Sheet's actual header row (sheet-template.csv) and the
Config node's field list (build-spec.md, Workflow 1 step 3). No column here is
invented. Writes erd-real.html; render with headless Chrome (command printed at
the end).

    python3 docs/gen_erd.py
"""

from __future__ import annotations

import csv
import html
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SHEET_CSV = ROOT / "sheet-template.csv"
BUILD_SPEC = ROOT / "build-spec.md"
W, H = 1500, 640
ACCENT, PKBG, DOT = "#c2410c", "#ffedd5", "#fff7ed"


def sheet_columns() -> list[str]:
    with open(SHEET_CSV) as f:
        return next(csv.reader(f))


def config_fields() -> list[tuple[str, str]]:
    text = BUILD_SPEC.read_text()
    section = re.search(r"\*\*Set — Config\*\*.*?(?=\n\d\. \*\*)", text, re.S)
    body = section.group(0) if section else text
    return re.findall(r"`(\w+)`\s*\((\w+)", body)


TICKET_PK = "ticket_id"
CONFIG_PK = "business_name"


def card(name, cols, x, y, pk_field=None, fk_field=None, fk_target=None):
    lis = []
    for cname, ctype in cols:
        badge = ""
        if cname == pk_field:
            badge = '<span class="k pk">PK</span>'
        elif cname == fk_field:
            badge = '<span class="k fk">FK</span>'
        lis.append(f'<li>{badge}<span class="nm">{html.escape(cname)}</span>'
                   f'<span class="ty">{html.escape(ctype)}</span></li>')
    return (f'<div class="entity" style="left:{x}px; top:{y}px;">'
            f'<div class="h">{html.escape(name)}</div><ul>{"".join(lis)}</ul></div>')


CSS = """<style>
 :root {{ --accent:{accent}; --pkbg:{pkbg}; --dot:{dot}; }}
 *{{box-sizing:border-box;margin:0;padding:0;}} html,body{{width:{W}px;height:{H}px;}}
 body{{font-family:-apple-system,'Helvetica Neue',Arial,sans-serif;color:#0f172a;background:#fff;position:relative;}}
 .bg{{position:absolute;inset:0;background-image:radial-gradient(var(--dot) 1.4px,transparent 1.4px);background-size:26px 26px;opacity:.55;}}
 header{{position:absolute;top:28px;left:44px;z-index:5;}} h1{{font-size:27px;letter-spacing:-.02em;}} h1 .tag{{color:var(--accent);}}
 .sub{{color:#64748b;font-size:13.5px;margin-top:5px;max-width:1100px;}}
 .legend{{position:absolute;top:32px;right:46px;z-index:5;display:flex;gap:16px;align-items:center;font-size:12.5px;color:#475569;}}
 .legend .k{{font-size:9px;font-weight:700;padding:1px 5px;border-radius:4px;margin-right:5px;}}
 .pk{{background:var(--pkbg);color:var(--accent);}} .fk{{background:#f1f5f9;color:#64748b;}}
 .zone{{position:absolute;z-index:0;border:1.5px dashed;border-radius:16px;}}
 .zone-label{{position:absolute;z-index:1;font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#475569;}}
 svg.lines{{position:absolute;inset:0;z-index:1;}}
 .entity{{position:absolute;z-index:2;width:260px;background:#fff;border:1px solid #e2e8f0;border-radius:12px;box-shadow:0 6px 20px rgba(15,23,42,.08);overflow:hidden;}}
 .entity .h{{background:var(--accent);color:#fff;font-weight:700;font-size:14px;padding:9px 13px;}}
 .entity ul{{list-style:none;padding:6px 0;}}
 .entity li{{font-size:11.5px;padding:2.5px 13px;display:flex;align-items:center;gap:7px;color:#334155;}}
 .entity li .nm{{flex:1;}} .entity li .ty{{color:#94a3b8;font-size:9.5px;}}
 .entity li .k{{font-size:8.5px;font-weight:700;padding:1px 5px;border-radius:4px;}}
 .rel{{fill:#64748b;font-size:12px;font-weight:700;}}
 .verb{{fill:{accent};font-size:11.5px;font-style:italic;}}
 .note{{position:absolute;z-index:2;width:250px;font-size:11.5px;color:#7c2d12;background:#fff7ed;
        border:1px dashed #fb923c;border-radius:10px;padding:10px 12px;line-height:1.5;}}
</style>"""


def main():
    sheet_cols_raw = sheet_columns()
    sheet_cols = [(c, "string") for c in sheet_cols_raw]
    for numeric in ("received_at", "approved_at"):
        sheet_cols = [(c, "datetime" if c == numeric else t) for c, t in sheet_cols]
    for enum_col in ("urgency",):
        sheet_cols = [(c, "enum" if c == enum_col else t) for c, t in sheet_cols]
    sheet_cols = [(c, "enum" if c == "status" else t) for c, t in sheet_cols]

    cfg = config_fields()
    if not cfg:
        cfg = [("business_name", "string"), ("business_type", "string"),
               ("categories", "string"), ("webhook_secret", "string"),
               ("sheet_id", "string"), ("sheet_tab", "string")]

    ticket_card = card("tickets (Google Sheet row)", sheet_cols, 480, 190,
                       pk_field=TICKET_PK)
    config_card = card("Config (n8n Set node)", cfg, 60, 190, pk_field=CONFIG_PK)

    zones = (
        '<div class="zone" style="left:30px;top:150px;width:360px;height:260px;'
        'background:rgba(194,65,12,.05);border-color:rgba(194,65,12,.3);"></div>'
        '<div class="zone-label" style="left:46px;top:162px;">Per-business config</div>'
        '<div class="zone" style="left:440px;top:150px;width:390px;height:440px;'
        'background:rgba(2,132,199,.05);border-color:rgba(2,132,199,.3);"></div>'
        '<div class="zone-label" style="left:456px;top:162px;">Data store</div>'
    )

    note1 = ('<div class="note" style="left:60px;top:440px;">One config block per business: '
             'change business_name, business_type, categories and webhook_secret; '
             'everything downstream reads from it. No other node is edited per client.</div>')
    note2 = ('<div class="note" style="left:900px;top:190px;">No relational DB. '
             'One flat sheet is the store; a row is created on intake and updated '
             'in place by the approval watcher (matched on ticket_id).</div>')

    svg = (
        f'<svg class="lines" width="{W}" height="{H}">'
        '<path d="M420,270 H480" stroke="#94a3b8" stroke-width="2" fill="none"/>'
        '<text class="verb" x="450" y="255" text-anchor="middle">configures</text>'
        '</svg>'
    )

    legend = (
        '<div class="legend">'
        '<span><span class="k pk">PK</span>identifying field</span>'
        '<span>Gemini fills: urgency, topic, draft_reply</span></div>')

    page = ("<!doctype html><html><head><meta charset='utf-8'>"
            + CSS.format(accent=ACCENT, pkbg=PKBG, dot=DOT, W=W, H=H)
            + "</head><body><div class='bg'></div>"
            "<header><h1>TriagePilot <span class='tag'>&mdash; data model</span></h1>"
            f"<div class='sub'>Parsed from the real sources in this repo: the Sheet's header row "
            f"(sheet-template.csv) and the Config node's field list (build-spec.md). No live database "
            f"&mdash; the store is a single Google Sheet, one row per ticket.</div></header>"
            + legend + zones + svg + ticket_card + config_card + note1 + note2
            + "</body></html>")
    (HERE / "erd-real.html").write_text(page)
    print(f"wrote erd-real.html ({len(sheet_cols)} sheet cols, {len(cfg)} config fields)\nRender:")
    print(f'  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless '
          f'--disable-gpu --hide-scrollbars --force-device-scale-factor=2 '
          f'--window-size={W},{H} --screenshot="{HERE}/erd-real.png" "file://{HERE}/erd-real.html"')


if __name__ == "__main__":
    main()
