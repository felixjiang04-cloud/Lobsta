"""Run a folder of REAL invoice photos through Lobsta, oldest first, and write
down everything it finds. This is the opening line of the pitch:
"we ran my mum's last three months of invoices and found $X".

  export ANTHROPIC_API_KEY=...
  python -m scripts.find_money --photos data/mum --profile sushi --out report

Reads are cached next to each photo as <name>.read.json, so re-running is free.
Writes report/report.html (open it, screenshot it) and report/findings.json.
Lines that match nothing in the config still get tracked, under their printed name.
"""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

from lobsta import checks, config, i18n, pipeline, reader
from lobsta.config import item_name
from lobsta.matcher import norm_desc
from lobsta.store import Store


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--photos", required=True)
    ap.add_argument("--profile", default="sushi")
    ap.add_argument("--out", default="report")
    ap.add_argument("--backend", default=None)
    ap.add_argument("--lang", default="en", help="language of the report (en, fr, zh)")
    a = ap.parse_args()
    cfg = config.load(a.profile)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    db = out / "report.db"
    db.unlink(missing_ok=True)
    store = Store(str(db))
    reads = []
    for p in sorted(Path(a.photos).iterdir()):
        if p.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
            continue
        cache = p.with_suffix(".read.json")
        if cache.exists():
            raw = json.loads(cache.read_text(encoding="utf-8"))
        else:
            try:
                raw = reader.read_invoice(str(p), a.backend)
            except Exception as e:
                print("could not read", p.name, e)
                continue
            cache.write_text(json.dumps(raw, ensure_ascii=False, indent=1), encoding="utf-8")
        reads.append((p, raw))
        print("read", p.name)
    reads.sort(key=lambda r: str(r[1].get("date") or ""))
    findings, total_spend, unreadable = [], 0.0, []
    for p, raw in reads:
        res = pipeline.process(str(p), cfg, store, raw=raw)
        inv = res["invoice"]
        if not inv["lines"] or inv["total"] is None:
            unreadable.append(p.name)
            continue
        for ln in inv["lines"]:                      # track everything, even items not in the config
            ln["item_key"] = ln.get("item_key") or norm_desc(ln["description"]) or None
        for f in res["errors"] + res["alerts"]:
            if f["code"] in ("duplicate", "price_drop"):
                continue
            money = max(0, f.get("diff", 0)) if f["code"] == "line_math" else f.get("extra", 0) if f["code"] in ("price_jump", "shrink") else 0
            findings.append({"photo": p.name, "date": inv["date"], "supplier": inv["supplier"], "code": f["code"],
                             "money": round(money, 2), "text": i18n.flag_text(f, inv, cfg, a.lang)})
        if not any(f["code"] == "duplicate" for f in res["errors"]):
            store.confirm(res["id"], inv)
            total_spend += inv["total"]
    found = round(sum(f["money"] for f in findings), 2)
    # biggest price movers over the whole period
    movers = []
    for (key,) in store.db.execute("select distinct item_key from lines where item_key is not null"):
        h = store.price_history(key, limit=200)
        h = [r for r in h if r["cost_per"] == h[0]["cost_per"]]
        if len(h) >= 3 and h[-1]["unit_cost"] > 0:
            first, last = h[-1], h[0]
            movers.append({"item": item_name(cfg, key, a.lang), "from": first["unit_cost"], "to": last["unit_cost"],
                           "per": last["cost_per"], "first": first["date"], "last": last["date"], "n": len(h),
                           "pct": round((last["unit_cost"] / first["unit_cost"] - 1) * 100, 1)})
    movers.sort(key=lambda m: -m["pct"])
    summary = {"invoices": len(reads) - len(unreadable), "unreadable": unreadable, "total_spend": round(total_spend, 2),
               "money_found": found, "findings": findings, "movers": movers[:10]}
    (out / "findings.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    e = html.escape
    rows = "".join(f"<tr><td>{e(f['date'] or '')}</td><td>{e(f['supplier'])}</td><td>{e(f['text'])}</td>"
                   f"<td class=n>{'$%.2f' % f['money'] if f['money'] else ''}</td></tr>" for f in findings)
    mrows = "".join(f"<tr><td>{e(m['item'])}</td><td class=n>${m['from']:.2f}</td><td class=n>${m['to']:.2f}/{e(m['per'])}</td>"
                    f"<td class=n>{m['pct']:+.1f}%</td><td>{e(m['first'])} to {e(m['last'])} ({m['n']} invoices)</td></tr>"
                    for m in movers[:10])
    (out / "report.html").write_text(f"""<!doctype html><meta charset=utf-8><title>Lobsta: what we found</title>
<style>body{{font:17px/1.5 -apple-system,Segoe UI,"PingFang SC","Noto Sans SC",sans-serif;max-width:980px;margin:32px auto;padding:0 20px;color:#1f1b16;background:#f6f1e9}}
.k{{display:flex;gap:16px;flex-wrap:wrap}}.k div{{flex:1;min-width:200px;background:#fffdf9;border:1px solid #e4dccf;border-radius:14px;padding:16px}}
.k b{{display:block;font-size:40px;line-height:1.1}}.k .hit{{background:#c8372d;color:#fff;border-color:#c8372d}}
table{{width:100%;border-collapse:collapse;background:#fffdf9;border:1px solid #e4dccf;margin:10px 0 28px}}td,th{{padding:9px 12px;border-bottom:1px solid #e4dccf;text-align:left;vertical-align:top}}
.n{{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}}h2{{margin-top:30px}}small{{color:#7a7065}}</style>
<h1>What Lobsta found in {e(cfg.get('business') or '')}'s invoices</h1>
<div class=k><div class=hit><b>${found:,.2f}</b>overcharges, price jumps and shrunken packs</div>
<div><b>{summary['invoices']}</b>invoices read</div><div><b>${total_spend:,.0f}</b>purchases covered</div></div>
<h2>Findings</h2><table><tr><th>Date</th><th>Supplier</th><th>What</th><th class=n>Cost</th></tr>{rows or '<tr><td colspan=4>Nothing flagged.</td></tr>'}</table>
<h2>Biggest price moves</h2><table><tr><th>Item</th><th class=n>First</th><th class=n>Latest</th><th class=n>Change</th><th>Period</th></tr>{mrows or '<tr><td colspan=5>Need at least 3 invoices per item.</td></tr>'}</table>
<small>Every figure here is arithmetic on numbers read from the invoices. A flagged line can also be a misread:
check each finding against its photo before quoting it. Unreadable photos: {e(', '.join(unreadable) or 'none')}.</small>""",
                                         encoding="utf-8")
    print(f"\n{summary['invoices']} invoices, ${found:,.2f} found. Open {out / 'report.html'}")


if __name__ == "__main__":
    main()
