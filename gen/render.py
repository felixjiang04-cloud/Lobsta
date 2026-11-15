"""Draw an invoice (the reader-format dict plus print details) to an image.
Three layouts so the model doesn't learn one template: grid, plain, cn."""
from __future__ import annotations

import random

from PIL import Image, ImageDraw, ImageFont

W, H = 1240, 1754
# (regular, bold, ttc index) candidates per family: Linux first, then Windows, then macOS.
_LIN, _WIN, _MAC = "/usr/share/fonts", "C:/Windows/Fonts", "/System/Library/Fonts"
FONTS = {
    "sans": [(f"{_LIN}/truetype/liberation/LiberationSans-Regular.ttf", f"{_LIN}/truetype/liberation/LiberationSans-Bold.ttf", 0),
             (f"{_WIN}/arial.ttf", f"{_WIN}/arialbd.ttf", 0),
             (f"{_MAC}/Supplemental/Arial.ttf", f"{_MAC}/Supplemental/Arial Bold.ttf", 0)],
    "serif": [(f"{_LIN}/truetype/liberation/LiberationSerif-Regular.ttf", f"{_LIN}/truetype/liberation/LiberationSerif-Bold.ttf", 0),
              (f"{_WIN}/times.ttf", f"{_WIN}/timesbd.ttf", 0),
              (f"{_MAC}/Supplemental/Times New Roman.ttf", f"{_MAC}/Supplemental/Times New Roman Bold.ttf", 0)],
    "mono": [(f"{_LIN}/truetype/liberation/LiberationMono-Regular.ttf", f"{_LIN}/truetype/liberation/LiberationMono-Bold.ttf", 0),
             (f"{_WIN}/cour.ttf", f"{_WIN}/courbd.ttf", 0),
             (f"{_MAC}/Supplemental/Courier New.ttf", f"{_MAC}/Supplemental/Courier New Bold.ttf", 0)],
    "dejavu": [(f"{_LIN}/truetype/dejavu/DejaVuSans.ttf", f"{_LIN}/truetype/dejavu/DejaVuSans-Bold.ttf", 0),
               (f"{_WIN}/verdana.ttf", f"{_WIN}/verdanab.ttf", 0),
               (f"{_MAC}/Supplemental/Verdana.ttf", f"{_MAC}/Supplemental/Verdana Bold.ttf", 0)],
    "cjk": [(f"{_LIN}/opentype/noto/NotoSansCJK-Regular.ttc", f"{_LIN}/opentype/noto/NotoSansCJK-Bold.ttc", 2),
            (f"{_WIN}/msyh.ttc", f"{_WIN}/msyhbd.ttc", 0),
            (f"{_MAC}/PingFang.ttc", f"{_MAC}/PingFang.ttc", 0),
            (f"{_MAC}/STHeiti Light.ttc", f"{_MAC}/STHeiti Medium.ttc", 0)],
    "cjkserif": [(f"{_LIN}/opentype/noto/NotoSerifCJK-Regular.ttc", f"{_LIN}/opentype/noto/NotoSerifCJK-Bold.ttc", 2),
                 (f"{_WIN}/simsun.ttc", f"{_WIN}/simsun.ttc", 0),
                 (f"{_MAC}/Supplemental/Songti.ttc", f"{_MAC}/Supplemental/Songti.ttc", 0)],
}
FALLBACK = {"cjkserif": "cjk", "serif": "sans", "mono": "sans", "dejavu": "sans"}
_cache = {}


def _pick(family: str):
    import os
    for reg, bd, idx in FONTS[family]:
        if os.path.exists(reg) and os.path.exists(bd):
            return reg, bd, idx
    if family in FALLBACK:
        return _pick(FALLBACK[family])
    raise RuntimeError(
        f"No font found for '{family}'. On Linux: apt-get install -y fonts-liberation fonts-dejavu-core fonts-noto-cjk")


def font(family: str, size: int, bold: bool = False):
    k = (family, size, bold)
    if k not in _cache:
        reg, bd, idx = _pick(family)
        _cache[k] = ImageFont.truetype(bd if bold else reg, size, index=idx)
    return _cache[k]


L = {  # labels printed on the page
 "fr": dict(title="FACTURE", no="No facture", date="Date", sold="Vendu à", code="Code", desc="Description",
            qty="Qté", unit="Unité", price="Prix unit.", amount="Montant", sub="Sous-total", total="TOTAL",
            terms="Termes : net 15 jours", thanks="Merci de votre commande!", page="Page 1 de 1"),
 "en": dict(title="INVOICE", no="Invoice #", date="Date", sold="Sold to", code="Item", desc="Description",
            qty="Qty", unit="Unit", price="Unit price", amount="Amount", sub="Subtotal", total="TOTAL",
            terms="Terms: net 15 days", thanks="Thank you for your business!", page="Page 1 of 1"),
 "zh": dict(title="送货单 / INVOICE", no="单号", date="日期", sold="客户", code="编号", desc="品名规格",
            qty="数量", unit="单位", price="单价", amount="金额", sub="小计", total="总计",
            terms="货到请当面点清", thanks="多谢惠顾！", page=""),
}


def render(inv: dict, pr: dict, rng: random.Random) -> Image.Image:
    """inv: label dict (strings as printed). pr: print details
    {style, lang, date_text, address, phone, customer, cur_prefix, cur_suffix}."""
    lang, style = pr["lang"], pr["style"]
    lab = L[lang]
    cjk = lang == "zh" or any(ord(c) > 0x2E7F for c in inv["supplier"])
    fam = rng.choice(["cjk", "cjkserif"]) if cjk else {"grid": rng.choice(["sans", "dejavu", "serif"]),
                                                      "plain": rng.choice(["mono", "sans"]),
                                                      "cn": "cjk"}[style]
    base = rng.choice([22, 23, 24, 25]) if style != "cn" else rng.choice([25, 26, 27])
    f, fb, fs = font(fam, base), font(fam, base, True), font(fam, base - 4)
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    ink = rng.choice([(20, 20, 20), (35, 35, 45), (25, 30, 60)])
    mx = rng.randint(70, 100)
    y = rng.randint(60, 100)
    money = lambda s: f"{pr['cur_prefix']}{s}{pr['cur_suffix']}" if s != "" else ""

    # header
    tx = W - mx - 380
    hs = base + rng.choice([12, 16, 20])
    while hs > base and d.textlength(inv["supplier"], font=font(fam, hs, True)) > tx - mx - 30:
        hs -= 2
    d.text((mx, y), inv["supplier"], font=font(fam, hs, True), fill=ink)
    y += base + 34
    for line in pr["address"] + [("Tél. : " if lang == "fr" else "Tel: ") + pr["phone"]]:
        d.text((mx, y), line, font=fs, fill=ink)
        y += base + 2
    d.text((tx, 80), lab["title"], font=font(fam, base + 10, True), fill=ink)
    d.text((tx, 80 + base + 26), f"{lab['no']} : {inv['invoice_number']}", font=f, fill=ink)
    d.text((tx, 80 + 2 * base + 34), f"{lab['date']} : {pr['date_text']}", font=f, fill=ink)
    y = max(y, 80 + 3 * base + 50) + 24
    d.text((mx, y), f"{lab['sold']} : {pr['customer'][0]}", font=fb, fill=ink)
    y += base + 6
    d.text((mx, y), pr["customer"][1], font=fs, fill=ink)
    y += base + 34

    # table
    show_code = pr.get("show_code", True)
    cols = [("code", 130 if show_code else 0, "l"), ("desc", 0, "l"), ("qty", 110, "r"), ("unit", 110, "c"),
            ("price", 170, "r"), ("amount", 180, "r")]
    fixed = sum(c[1] for c in cols)
    xs, x = [], mx
    for name, w, al in cols:
        if name == "desc":
            w = W - 2 * mx - fixed
        xs.append((name, x, w, al))
        x += w
    row_h = base + rng.choice([14, 18, 22])
    grid = style in ("grid", "cn")

    def cell(text, x0, w, al, yy, fnt):
        tw = d.textlength(text, font=fnt)
        px = x0 + 8 if al == "l" else (x0 + w - 8 - tw if al == "r" else x0 + (w - tw) / 2)
        d.text((px, yy + (row_h - base) / 2 - 2), text, font=fnt, fill=ink)

    if style == "grid":
        d.rectangle([mx, y, W - mx, y + row_h], fill=rng.choice([(225, 225, 225), (210, 222, 235), (235, 228, 210)]))
    for name, x0, w, al in xs:
        if w and (name != "code" or show_code):
            cell(lab[name], x0, w, al, y, fb)
    top = y
    y += row_h
    d.line([mx, y, W - mx, y], fill=ink, width=2)
    for ln in inv["lines"]:
        desc = ln["description"]
        while d.textlength(desc, font=f) > xs[1][2] - 16 and len(desc) > 4:
            desc = desc[:-1]
        vals = {"code": ln.get("code") or "", "desc": desc, "qty": ln["quantity"], "unit": ln["unit"],
                "price": money(ln["unit_price"]), "amount": money(ln["line_total"])}
        for name, x0, w, al in xs:
            if w and (name != "code" or show_code):
                cell(vals[name], x0, w, al, y, f)
        y += row_h
        if grid:
            d.line([mx, y, W - mx, y], fill=(150, 150, 150), width=1)
    for _ in range(rng.randint(0, 3) if grid else 0):   # blank ruled rows, like real pads
        y += row_h
        d.line([mx, y, W - mx, y], fill=(150, 150, 150), width=1)
    if grid:
        for name, x0, w, al in xs:
            if w:
                d.line([x0, top, x0, y], fill=(150, 150, 150), width=1)
        d.rectangle([mx, top, W - mx, y], outline=ink, width=2)
    else:
        d.line([mx, y + 4, W - mx, y + 4], fill=ink, width=1)

    # totals
    y += 26
    lx, rx = W - mx - 430, W - mx - 8
    rows = [(lab["sub"], inv["subtotal"], False)] + [(t["name"], t["amount"], False) for t in inv["taxes"]] \
        + [(lab["total"], inv["total"], True)]
    for name, val, bold in rows:
        fnt = fb if bold else f
        if bold:
            d.line([lx, y - 4, W - mx, y - 4], fill=ink, width=2)
        d.text((lx, y), name, font=fnt, fill=ink)
        s = money(val)
        d.text((rx - d.textlength(s, font=fnt), y), s, font=fnt, fill=ink)
        y += row_h
    if pr.get("tax_note"):
        d.text((mx, y - 2 * row_h), pr["tax_note"], font=fs, fill=ink)
    y += 30
    for line in (lab["terms"], lab["thanks"]):
        d.text((mx, y), line, font=fs, fill=ink)
        y += base + 6
    if pr.get("stamp"):   # handwritten-ish "received" mark
        sx, sy = rng.randint(mx + 300, W - 500), min(y + rng.randint(10, 80), H - 160)
        d.ellipse([sx, sy, sx + 250, sy + 95], outline=(190, 40, 40), width=4)
        d.text((sx + 42, sy + 28), pr["stamp"], font=font("cjk" if cjk else "sans", 28, True), fill=(190, 40, 40))
    if lab["page"]:
        d.text((W - mx - 150, H - 70), lab["page"], font=fs, fill=ink)
    return img
