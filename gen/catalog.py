"""Invented suppliers and products for the two demo restaurants. Supplier names
are made up; prices are plausible Montreal wholesale numbers, not real quotes.

Product tuple: (item_key, code, mode, price, names, packs, qty_range)
  mode 'w'  sold by weight: unit kg or lb, price is per that unit
  mode 'c'  sold by the case/bag: packs = pack texts printed in the description
  mode 'e'  sold each
names: {lang: text as printed}
"""

def P(key, code, mode, price, names, packs=None, qty=(1, 6), unit=None, taxable=False):
    return dict(key=key, code=code, mode=mode, price=price, names=names, packs=packs or [""], qty=qty,
                unit=unit, taxable=taxable)

SUPPLIERS = {
 "baie_nord": dict(
    name="Poissonnerie Baie-Nord inc.", langs=["fr"], style="grid",
    address=["4410 rue des Quais", "Montréal (Québec) H0H 0H0"], phone="514 555-0142", prefix="BN",
    products=[
      P("salmon", "1001", "w", 17.50, {"fr": "Saumon atl. frais filet", "en": "Atl. salmon fillet fresh"}, qty=(8, 16), unit="kg"),
      P("tuna", "1014", "w", 34.00, {"fr": "Thon albacore saku", "en": "Yellowfin tuna saku"}, qty=(2, 6), unit="kg"),
      P("hamachi", "1022", "w", 29.75, {"fr": "Hamachi filet congelé", "en": "Hamachi fillet frozen"}, qty=(1, 4), unit="kg"),
      P("shrimp", "1103", "c", 52.00, {"fr": "Crevettes ebi 30 un", "en": "Ebi shrimp 30 ct"}, ["10 x 255 g", "10 x 240 g"], (1, 3)),
      P("tobiko", "1210", "e", 21.50, {"fr": "Tobiko orange", "en": "Tobiko orange"}, ["500 g"], (1, 4)),
      P("crabstick", "1305", "c", 38.00, {"fr": "Goberge kamaboko", "en": "Kamaboko crab stick"}, ["10 x 1 kg"], (1, 2)),
      P("eel", "1330", "c", 96.00, {"fr": "Anguille unagi grillée", "en": "Unagi kabayaki"}, ["5 kg"], (1, 2)),
      P("scallop", "1120", "w", 41.00, {"fr": "Pétoncles U10", "en": "Scallops U10"}, qty=(1, 3), unit="kg"),
    ]),
 "asie_quebec": dict(
    name="Distribution Asie-Québec", langs=["fr", "en"], style="plain",
    address=["9200 boul. Industriel, local 12", "Montréal (Québec) H0H 0H0"], phone="514 555-0178", prefix="AQ",
    products=[
      P("rice", "R-200", "c", 38.50, {"fr": "Riz Calrose", "en": "Calrose rice"}, ["20 kg", "18 kg"], (2, 6), unit="sac"),
      P("nori", "N-050", "e", 4.50, {"fr": "Nori feuilles 50 un", "en": "Nori sheets 50 ct"}, [""], (6, 20)),
      P("rice_vinegar", "V-378", "c", 31.00, {"fr": "Vinaigre de riz", "en": "Rice vinegar"}, ["4 x 3,78 L"], (1, 3)),
      P("soy_sauce", "S-180", "c", 44.00, {"fr": "Sauce soya", "en": "Soy sauce"}, ["6 x 1,8 L"], (1, 3)),
      P("wasabi", "W-100", "e", 14.25, {"fr": "Poudre de wasabi", "en": "Wasabi powder"}, ["1 kg"], (1, 4)),
      P("ginger", "G-010", "e", 27.00, {"fr": "Gingembre mariné gari", "en": "Pickled ginger gari"}, ["10 kg"], (1, 2)),
      P("sesame", "E-005", "e", 19.50, {"fr": "Graines de sésame grillées", "en": "Roasted sesame seeds"}, ["5 kg"], (1, 2)),
      P("panko", "P-454", "c", 26.00, {"fr": "Chapelure panko", "en": "Panko breadcrumbs"}, ["10 x 454 g"], (1, 3)),
      P("tempura", "T-900", "c", 33.00, {"fr": "Farine tempura", "en": "Tempura flour"}, ["20 x 700 g"], (1, 2)),
      P("edamame", "D-454", "c", 29.00, {"fr": "Edamame congelé", "en": "Frozen edamame"}, ["20 x 454 g"], (1, 3)),
      P("containers", "X-900", "c", 42.00, {"fr": "Contenants à emporter", "en": "Takeout containers"}, ["500 un"], (1, 3), taxable=True),
    ]),
 "marche_soleil": dict(
    name="Fruits et Légumes Marché Soleil", langs=["fr"], style="grid",
    address=["250 av. du Marché Central", "Montréal (Québec) H0H 0H0"], phone="514 555-0116", prefix="MS",
    products=[
      P("avocado", "AV48", "c", 46.00, {"fr": "Avocat Hass 48 un"}, [""], (1, 4)),
      P("cucumber", "CC24", "c", 22.50, {"fr": "Concombre anglais 12 un"}, [""], (1, 4)),
      P("mango", "MG09", "c", 14.00, {"fr": "Mangue Ataulfo"}, ["4 kg"], (1, 3)),
      P("green_onion", "OV48", "c", 28.00, {"fr": "Oignon vert 48 bottes"}, [""], (1, 2)),
      P("carrot", "CA50", "c", 24.00, {"fr": "Carotte jumbo"}, ["50 lb", "45 lb"], (1, 2), unit="sac"),
      P("lettuce", "LT24", "c", 31.00, {"fr": "Laitue iceberg 24 un"}, [""], (1, 2)),
      P("lemon", "CI115", "c", 39.00, {"fr": "Citron 115 un"}, [""], (1, 2)),
    ]),
 "hong_yun": dict(
    name="鸿运食品批发 Hong Yun Foods", langs=["zh"], style="cn",
    address=["7755 rue Saint-Exemple", "Montréal QC H0H 0H0"], phone="514 555-0188", prefix="HY",
    products=[
      P("beef_roll", "F01", "w", 6.80, {"zh": "肥牛卷"}, qty=(20, 60), unit="磅"),
      P("lamb_roll", "F02", "w", 8.20, {"zh": "羊肉卷"}, qty=(10, 40), unit="磅"),
      P("tripe", "F07", "w", 5.50, {"zh": "牛百叶"}, qty=(5, 20), unit="磅"),
      P("shrimp_paste", "S03", "c", 58.00, {"zh": "虾滑"}, ["20 x 150g"], (1, 4)),
      P("fish_ball", "S10", "c", 36.00, {"zh": "鱼丸"}, ["10 x 500g"], (1, 4)),
      P("duck_blood", "D02", "c", 30.00, {"zh": "鸭血"}, ["24 x 300g"], (1, 3)),
      P("luncheon", "C05", "c", 62.00, {"zh": "午餐肉"}, ["24 x 340g"], (1, 2)),
    ]),
 "xin_xian": dict(
    name="新鲜蔬果行 Fruits & Légumes Xin Xian", langs=["zh"], style="cn",
    address=["120 rue du Marché-Exemple", "Montréal QC H0H 0H0"], phone="514 555-0131", prefix="XX",
    products=[
      P("napa", "V01", "c", 26.00, {"zh": "大白菜"}, ["50磅", "45磅"], (1, 5)),
      P("enoki", "V05", "c", 18.00, {"zh": "金针菇"}, ["25 x 200g", "25 x 150g"], (1, 5)),
      P("potato", "V08", "c", 21.00, {"zh": "土豆"}, ["50磅"], (1, 3), unit="袋"),
      P("lotus", "V11", "w", 3.20, {"zh": "莲藕"}, qty=(10, 30), unit="磅"),
      P("bean_sprout", "V14", "c", 9.50, {"zh": "豆芽"}, ["10磅"], (1, 4), unit="袋"),
      P("cilantro", "V20", "c", 24.00, {"zh": "香菜 30把"}, [""], (1, 2)),
      P("tofu", "T01", "c", 19.00, {"zh": "老豆腐"}, ["12 x 454g"], (1, 4)),
    ]),
 "long_ji": dict(
    name="龙记干货 Épicerie en gros Long Ji", langs=["zh", "en"], style="plain",
    address=["88 boul. de l'Exemple", "Brossard QC H0H 0H0"], phone="450 555-0164", prefix="LJ",
    products=[
      P("soup_base", "B01", "c", 78.00, {"zh": "麻辣火锅底料", "en": "Spicy hotpot base"}, ["40 x 200g"], (1, 4)),
      P("wide_noodle", "N02", "c", 34.00, {"zh": "宽粉", "en": "Wide glass noodle"}, ["30 x 400g"], (1, 3)),
      P("yuba", "N07", "c", 41.00, {"zh": "腐竹", "en": "Dried bean curd stick"}, ["20 x 250g"], (1, 2)),
      P("sesame_paste", "S01", "c", 55.00, {"zh": "芝麻酱", "en": "Sesame paste"}, ["12 x 450g"], (1, 2)),
      P("chili", "C01", "e", 23.00, {"zh": "干辣椒", "en": "Dried chili"}, ["5磅"], (1, 3)),
      P("oil", "O20", "e", 46.00, {"zh": "食用油", "en": "Cooking oil"}, ["20 L"], (1, 3)),
      P("napkins", "X01", "c", 35.00, {"zh": "餐巾纸", "en": "Napkins"}, ["6000 张"], (1, 2), taxable=True),
    ]),
}
PROFILE_SUPPLIERS = {"sushi": ["baie_nord", "asie_quebec", "marche_soleil"],
                     "hotpot": ["hong_yun", "xin_xian", "long_ji"]}
CUSTOMERS = {"sushi": ["Sushi Demo", "3550 rue de l'Exemple, Montréal"],
             "hotpot": ["麻辣烫 Demo Malatang", "1200 rue de l'Exemple, Montréal"]}
