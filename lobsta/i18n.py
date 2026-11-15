"""Every sentence the owner sees, in their language. Numbers are filled in by
code; no model is involved in producing these."""
from __future__ import annotations

from .config import item_name

T = {
"en": {
 "line_math": "Line {line}: {qty:g} × {price} should be {expected}, but the invoice says {printed} ({diff} {dir}).",
 "subtotal_math": "The lines add up to {expected}, but the subtotal says {printed}.",
 "total_math": "Subtotal plus tax is {expected}, but the total says {printed}.",
 "missing_number": "Line {line}: I couldn't read a number. Please check it.",
 "no_lines": "I couldn't read any lines on this photo. Try a flatter, brighter shot.",
 "duplicate": "This looks like invoice {number} from {supplier}, which is already saved.",
 "price_jump": "{item} is {now}/{per} on this invoice. You paid {usual}/{per} the last {n} times: {pct}% more, {extra} extra today.",
 "price_drop": "{item} is down to {now}/{per} from {usual}/{per} ({pct}%).",
 "shrink": "{item}: same price ({case_price}), but the pack went from {before} kg to {now} kg. That is a hidden {pct}% increase.",
 "over": "over", "under": "under",
 "clean": "Everything adds up.", "saved": "Saved {n} lines from {supplier}. Total {total}.",
 "unknown_item": "Line {line}: which item is \"{desc}\"?",
 "spend": "You spent {total} on {item} from {start} to {end} ({qty:g} {unit}).",
 "spend_all": "You spent {total} from {start} to {end}. Biggest: {top}.",
 "stock_line": "{item}: {on_hand:g} {unit} left, about {days} days.",
 "stock_unknown": "{item}: no count yet.", "stock_none": "No counts yet. Say your closing counts and I'll track it.",
 "counted": "Counted: {items}.",
 "adj_line": "{item}: {sign}{qty:g} {unit}, now {now:g} {unit_now} on hand.",
 "reorder_none": "Nothing needs ordering before the next delivery.",
 "reorder_head": "Running out before the next delivery ({day}):",
 "reorder_line": "{item}: {on_hand:g} {unit} left, lasts {days} days. Order {order}.",
 "help": "Send an invoice photo, say your closing counts, or ask what you spent, what's left, or what to order.",
 "price_hist": "{item}: {points}.",
 "no_data": "I don't have any invoices for that yet.",
 "cmp_head": "Compared with {shops} shops in {area}{sim}:", "cmp_sim": " (simulated data for this demo)",
 "cmp_line": "{item}: you pay {mine}/{per}, the median is {median}/{per} ({pct}%).",
 "cmp_high": " Higher than 3 in 4 shops.", "cmp_low": " Lower than 3 in 4 shops.", "cmp_none": "I don't have prices from other shops for that yet.",
 "brief_order": "Running out before the next delivery ({day}): {items}.", "brief_order_none": "Stock covers you until the next delivery.",
 "brief_flags": "Problems on this week's invoices, worth {total}:", "brief_flags_none": "No problems on this week's invoices.",
 "brief_spend": "Spent this week: {this}. Last week: {last}.",
},
"fr": {
 "line_math": "Ligne {line} : {qty:g} × {price} devrait donner {expected}, mais la facture indique {printed} ({diff} {dir}).",
 "subtotal_math": "Les lignes totalisent {expected}, mais le sous-total indique {printed}.",
 "total_math": "Sous-total plus taxes = {expected}, mais le total indique {printed}.",
 "missing_number": "Ligne {line} : je n'ai pas pu lire un chiffre. Vérifiez-la.",
 "no_lines": "Je n'ai lu aucune ligne. Essayez une photo plus à plat et mieux éclairée.",
 "duplicate": "On dirait la facture {number} de {supplier}, déjà enregistrée.",
 "price_jump": "{item} est à {now}/{per} sur cette facture. Vous avez payé {usual}/{per} les {n} dernières fois : {pct} % de plus, soit {extra} de trop aujourd'hui.",
 "price_drop": "{item} baisse à {now}/{per} (avant {usual}/{per}, {pct} %).",
 "shrink": "{item} : même prix ({case_price}), mais le format passe de {before} kg à {now} kg. C'est une hausse cachée de {pct} %.",
 "over": "en trop", "under": "en moins",
 "clean": "Tous les calculs sont bons.", "saved": "{n} lignes enregistrées de {supplier}. Total {total}.",
 "unknown_item": "Ligne {line} : « {desc} » correspond à quel article ?",
 "spend": "Vous avez dépensé {total} en {item} du {start} au {end} ({qty:g} {unit}).",
 "spend_all": "Vous avez dépensé {total} du {start} au {end}. Le plus gros : {top}.",
 "stock_line": "{item} : il reste {on_hand:g} {unit}, environ {days} jours.",
 "stock_unknown": "{item} : pas encore de comptage.", "stock_none": "Aucun comptage pour l'instant. Dictez vos comptages de fermeture.",
 "counted": "Compté : {items}.",
 "adj_line": "{item} : {sign}{qty:g} {unit}, maintenant {now:g} {unit_now} en stock.",
 "reorder_none": "Rien à commander avant la prochaine livraison.",
 "reorder_head": "En rupture avant la prochaine livraison ({day}) :",
 "reorder_line": "{item} : reste {on_hand:g} {unit}, tient {days} jours. Commander {order}.",
 "help": "Envoyez une photo de facture, dictez vos comptages, ou demandez vos dépenses, votre stock ou quoi commander.",
 "price_hist": "{item} : {points}.",
 "no_data": "Je n'ai pas encore de factures pour ça.",
 "cmp_head": "Comparé à {shops} commerces à {area}{sim} :", "cmp_sim": " (données simulées pour cette démo)",
 "cmp_line": "{item} : vous payez {mine}/{per}, la médiane est {median}/{per} ({pct} %).",
 "cmp_high": " Plus cher que 3 commerces sur 4.", "cmp_low": " Moins cher que 3 commerces sur 4.", "cmp_none": "Je n'ai pas encore les prix d'autres commerces pour ça.",
 "brief_order": "{n} articles seront en rupture avant la prochaine livraison ({day}) : {items}.", "brief_order_none": "Le stock tient jusqu'à la prochaine livraison.",
 "brief_flags": "Problèmes sur les factures de la semaine, pour {total} :", "brief_flags_none": "Aucun problème sur les factures de la semaine.",
 "brief_spend": "Dépensé cette semaine : {this}. Semaine dernière : {last}.",
},
"zh": {
 "line_math": "第{line}行：{qty:g} × {price} 应该是 {expected}，但单子上写的是 {printed}（{dir}{diff}）。",
 "subtotal_math": "各行加起来是 {expected}，但小计写的是 {printed}。",
 "total_math": "小计加税应该是 {expected}，但总计写的是 {printed}。",
 "missing_number": "第{line}行：有个数字没看清，请检查一下。",
 "no_lines": "这张照片我没读出内容，请拍平一点、亮一点再试。",
 "duplicate": "这张好像是 {supplier} 的 {number} 号单，已经录过了。",
 "price_jump": "{item}这次是 {now}/{per}，前{n}次都是 {usual}/{per}，贵了 {pct}%，今天多付了 {extra}。",
 "price_drop": "{item}降到 {now}/{per}（之前 {usual}/{per}，{pct}%）。",
 "shrink": "{item}：价格没变（{case_price}），但每件从 {before} 公斤变成了 {now} 公斤，相当于偷偷涨了 {pct}%。",
 "over": "多收", "under": "少收",
 "clean": "数字都对得上。", "saved": "已保存 {supplier} 的 {n} 行，总计 {total}。",
 "unknown_item": "第{line}行：“{desc}”是哪样货？",
 "spend": "{start} 到 {end}，{item}一共花了 {total}（{qty:g} {unit}）。",
 "spend_all": "{start} 到 {end} 一共花了 {total}。最多的是：{top}。",
 "stock_line": "{item}：还剩 {on_hand:g} {unit}，大约够 {days} 天。",
 "stock_unknown": "{item}：还没盘点过。", "stock_none": "还没有盘点记录。收工时报一下数，我就能帮你盯着。",
 "counted": "已记录：{items}。",
 "adj_line": "{item}：{sign}{qty:g} {unit}，现在有 {now:g} {unit_now}。",
 "reorder_none": "下次送货之前都够用，不用订。",
 "reorder_head": "下次送货（{day}）之前会用完：",
 "reorder_line": "{item}：剩 {on_hand:g} {unit}，够 {days} 天。建议订 {order}。",
 "help": "可以发进货单照片、报今天的盘点，或者问我花了多少、还剩多少、该订什么。",
 "price_hist": "{item}：{points}。",
 "no_data": "这个还没有进货单数据。",
 "cmp_head": "和{area} {shops} 家店比{sim}：", "cmp_sim": "（演示用的模拟数据）",
 "cmp_line": "{item}：你付 {mine}/{per}，中位价 {median}/{per}（{pct}%）。",
 "cmp_high": "比四分之三的店都贵。", "cmp_low": "比四分之三的店都便宜。", "cmp_none": "这个还没有别家店的价格可以比。",
 "brief_order": "有 {n} 样货撑不到下次送货（{day}）：{items}。", "brief_order_none": "库存够用到下次送货。",
 "brief_flags": "这周的进货单有问题，一共 {total}：", "brief_flags_none": "这周的进货单没发现问题。",
 "brief_spend": "这周花了 {this}，上周 {last}。",
},
}
UNIT = {"zh": {"kg": "公斤", "l": "升", "case": "箱", "ea": "个", "bag": "袋", "lb": "磅", "jin": "斤", "g": "克"},
        "fr": {"case": "caisse", "ea": "un.", "bag": "sac"}, "en": {"ea": "pc"}}
PLURAL = {"en": {"bag": "bags", "case": "cases", "pc": "pcs", "box": "boxes"},
          "fr": {"caisse": "caisses", "sac": "sacs"}}


def money(v, lang: str = "en") -> str:
    if v is None:
        return "?"
    if lang == "fr":
        return f"{v:,.2f}".replace(",", " ").replace(".", ",") + " $"
    return f"${v:,.2f}"


def unit_word(u: str | None, lang: str, qty: float | None = None) -> str:
    """qty, when given, picks the plural: '3 bags', '1 bag' (Chinese has none)."""
    w = UNIT.get(lang, {}).get(u or "", u or "")
    if qty is not None and abs(qty) > 1:
        w = PLURAL.get(lang, {}).get(w, w)
    return w


def order_text(ln: dict, lang: str) -> str:
    """'3 袋 (60 公斤)' when the item is ordered by the pack, else '29 公斤'."""
    base = f"{ln['order']:g} {unit_word(ln['unit'], lang, ln['order'])}"
    if ln.get("order_packs"):
        return f"{ln['order_packs']:g} {unit_word(ln['order_unit'], lang, ln['order_packs'])} ({base})"
    return base


def t(lang: str, key: str, **kw) -> str:
    return T.get(lang, T["en"]).get(key, T["en"][key]).format(**kw)


def flag_text(flag: dict, inv: dict, cfg: dict, lang: str | None = None) -> str:
    lang = lang or cfg["owner_language"]
    m = lambda v: money(v, lang)
    c = flag["code"]
    ln = next((l for l in inv["lines"] if l["n"] == flag.get("line")), None)
    if c == "line_math":
        return t(lang, c, line=flag["line"], qty=ln["quantity"], price=m(ln["unit_price"]),
                 expected=m(flag["expected"]), printed=m(flag["printed"]), diff=m(abs(flag["diff"])),
                 dir=t(lang, "over" if flag["diff"] > 0 else "under"))
    if c in ("subtotal_math", "total_math"):
        return t(lang, c, expected=m(flag["expected"]), printed=m(flag["printed"]))
    if c in ("missing_number",):
        return t(lang, c, line=flag["line"])
    if c == "no_lines":
        return t(lang, c)
    if c == "duplicate":
        return t(lang, c, number=inv["invoice_number"], supplier=inv["supplier"])
    if c == "unknown_item":
        return t(lang, c, line=flag["line"], desc=ln["description"])
    item = item_name(cfg, flag.get("item_key"), lang)
    if c == "price_jump":
        return t(lang, c, item=item, now=m(flag.get("now_shown", flag["now"])), usual=m(flag.get("usual_shown", flag["usual"])),
                 per=unit_word(flag.get("per_shown", flag["per"]), lang),
                 pct=f"{flag['pct']:g}", extra=m(flag["extra"]), n=flag.get("n_prior", 4))
    if c == "price_drop":
        return t(lang, c, item=item, now=m(flag.get("now_shown", flag["now"])), usual=m(flag.get("usual_shown", flag["usual"])),
                 per=unit_word(flag.get("per_shown", flag["per"]), lang), pct=f"{flag['pct']:g}")
    if c == "shrink":
        return t(lang, c, item=item, case_price=m(flag["case_price"]), before=f"{flag['pack_before']:g}",
                 now=f"{flag['pack_now']:g}", pct=f"{flag['pct']:g}")
    return c
