"""منتخبات وشباب ونساء المنتخبات: يدمج بطولات Highlightly في «مجموعات» (كل مجموعة = دوري واحد في التطبيق).
python import_pools.py               جلب (يكمل من حيث توقف ويحترم الحصة) ثم تحميل في قاعدة البيانات
python import_pools.py --active      جلب المواسم الجارية فقط (للتحديث اليومي)
python import_pools.py --load        تحميل الملفات المحفوظة فقط (بلا طلبات)
python import_pools.py --names       كتابة أسماء المجموعات والدوريات النسائية في ملفات الترجمة
"""
import glob
import json
import os
import sys
import time

import importer
import provider

B = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(B, "pooldata")
LOCALES = os.path.join(B, "..", "docs", "locales")
ACTIVE_FROM = 2026
REFRESH_DAYS = 3
RESERVE = 45          # يترك هذا العدد من طلبات اليوم لسير العمل اليومي (يمرَّر --reserve 10 هناك)

N = lambda ar, en, fr, es, tr: {"ar": ar, "en": en, "fr": fr, "es": es, "tr": tr}
POOLS = [
    ("hlnatM", N("منتخبات الرجال", "National Teams (Men)", "Équipes nationales (hommes)", "Selecciones (hombres)", "Milli takımlar (erkek)"),
     [(25463, 2023), (26314, 2026), (27165, 2026), (28016, 2024), (28867, 2026), (29718, 2026), (32271, 2026), (31420, 2027), (5890, 2025),
      (5039, 2026), (4188, 2024), (817744, 2023), (8443, 2024), (22059, 2026), (30569, 2024), (456920, 2025), (1635, 2026), (9294, 2026)]),
    ("hlnatU23", N("منتخبات تحت 21 وتحت 23", "National U21/U23", "Sélections U21/U23", "Selecciones U21/U23", "Milli takımlar U21/U23"),
     [(33122, 2025), (724134, 2027), (864549, 2027), (453516, 2025), (810936, 2026), (811787, 2022), (773492, 2025), (917311, 2025), (1028792, 2026)]),
    ("hlnatU20", N("منتخبات تحت 19 وتحت 20", "National U19/U20", "Sélections U19/U20", "Selecciones U19/U20", "Milli takımlar U19/U20"),
     [(417774, 2025), (458622, 2026), (457771, 2026), (658607, 2025), (656905, 2026), (821999, 2026), (981987, 2024), (907950, 2025), (987093, 2026),
      (420327, 2026), (760727, 2027), (1061130, 2026), (795618, 2022)]),
    ("hlnatU17", N("منتخبات تحت 17", "National U17", "Sélections U17", "Selecciones U17", "Milli takımlar U17"),
     [(500321, 2026), (754770, 2027), (784555, 2026), (828807, 2026), (826254, 2026), (820297, 2025), (861996, 2027), (988795, 2024)]),
    ("hlnatW", N("منتخبات السيدات", "National Teams (Women)", "Équipes nationales (femmes)", "Selecciones (mujeres)", "Milli takımlar (kadın)"),
     [(7592, 2023), (749664, 2027), (789661, 2026), (567550, 2026), (785406, 2025), (633077, 2025), (922417, 2025), (885824, 2027), (788810, 2025),
      (761578, 2026), (891781, 2028), (1027090, 2025), (890930, 2024)]),
]
def _para_comps():
    f = os.path.join(B, "para_leagues.json")
    try:
        return [tuple(x) for x in json.load(open(f, encoding="utf-8"))]
    except Exception:
        return []


POOLS.append(("hlpara", N("كرة القدم للمعاقين", "Para football (disability)", "Football handisport", "Fútbol adaptado", "Engelli futbolu"), _para_comps()))
WOMEN = {
    "hl12698": N("دوري أبطال أوروبا للشباب", "UEFA Youth League", "Ligue des champions des jeunes", "Liga Juvenil de la UEFA", "UEFA Gençlik Ligi"),
    "hl758174": N("دوري النخبة تحت 20", "U20 Elite League", "Ligue élite U20", "Liga Élite Sub-20", "U20 Elit Ligi"),
    "hl775194": N("كأس فياريجو للشباب", "Viareggio Cup (Youth)", "Coupe de Viareggio (jeunes)", "Copa Viareggio (juvenil)", "Viareggio Kupası (gençler)"),
    "hl630524": N("الدوري البرازيلي تحت 20", "Brasileiro U20", "Brasileiro U20", "Brasileiro Sub-20", "Brasileiro U20"),
    "hl960712": N("الدوري البرازيلي تحت 17", "Brasileiro U17", "Brasileiro U17", "Brasileiro Sub-17", "Brasileiro U17"),
    "hl598186": N("الدوري الإنجليزي للشباب (PL2)", "Premier League 2 (England)", "Premier League 2 (Angleterre)", "Premier League 2 (Inglaterra)", "Premier League 2 (İngiltere)"),
    "hl38228": N("الدوري الإنجليزي النسائي (WSL)", "WSL (England)", "WSL (Angleterre)", "WSL (Inglaterra)", "WSL (İngiltere)"),
    "hl595633": N("الدرجة الثانية الإنجليزية النسائية", "Women's Championship (England)", "Championship féminin (Angleterre)", "Championship femenino (Inglaterra)", "Kadınlar Championship (İngiltere)"),
    "hl121626": N("الدوري الإسباني النسائي (ليغا إف)", "Liga F (Spain)", "Liga F (Espagne)", "Liga F (España)", "Liga F (İspanya)"),
    "hl55248": N("الدوري الفرنسي النسائي (D1)", "D1 Féminine (France)", "D1 Féminine (France)", "D1 Féminine (Francia)", "D1 Féminine (Fransa)"),
    "hl70566": N("الدوري الألماني النسائي", "Frauen-Bundesliga (Germany)", "Frauen-Bundesliga (Allemagne)", "Frauen-Bundesliga (Alemania)", "Frauen-Bundesliga (Almanya)"),
    "hl119073": N("الدوري الإيطالي النسائي", "Serie A Women (Italy)", "Serie A féminine (Italie)", "Serie A femenina (Italia)", "Serie A Kadınlar (İtalya)"),
    "hl216938": N("الدوري الأمريكي النسائي (NWSL)", "NWSL (USA)", "NWSL (États-Unis)", "NWSL (EE. UU.)", "NWSL (ABD)"),
}


def _age(path):
    try:
        d = json.load(open(path, encoding="utf-8"))
        return time.time() - d["t"] if isinstance(d, dict) else 10 ** 9
    except Exception:
        return 10 ** 9


def fetch(active_only=False, reserve=RESERVE):
    os.makedirs(DATA, exist_ok=True)
    client = provider.HighlightlyClient(reserve=reserve)
    got = 0
    for code, names, comps in POOLS:
        for cid, last in comps:
            for season in range(last - 2, last + 1):
                if active_only and season < ACTIVE_FROM:
                    continue
                path = os.path.join(DATA, "%s_%d_%d.json" % (code, cid, season))
                if os.path.exists(path):
                    if season < ACTIVE_FROM or _age(path) < REFRESH_DAYS * 86400:
                        continue
                try:
                    items, total = client.matches(cid, season)
                except provider.BudgetExhausted as e:
                    print("STOP: daily budget reached -", str(e)[:80], "| run again later (it resumes)")
                    return got
                except Exception as e:
                    print("FAILED", code, cid, season, str(e)[:80])
                    continue
                rows = [m for m in (provider.map_hl_match(x, code) for x in items) if m]
                json.dump({"t": time.time(), "rows": rows}, open(path, "w", encoding="utf-8"), ensure_ascii=False)
                got += 1
                print("saved", code, cid, season, len(rows), "matches | remaining today:", getattr(client, "remaining", "?"))
    return got


def load():
    total = 0
    for code, names, comps in POOLS:
        rows, seasons = [], []
        for path in sorted(glob.glob(os.path.join(DATA, code + "_*.json"))):
            try:
                part = json.load(open(path, encoding="utf-8"))
            except Exception:
                continue
            part = part["rows"] if isinstance(part, dict) else part
            for m in part:
                m["_teams"] = [tuple(t) for t in m.get("_teams", [])]
                seasons.append(m.get("season") or "")
            rows += part
        if not rows:
            continue
        n, t = importer._save(rows, "highlightly", {code: names["en"]}, max(seasons) or "", False)
        print(code, names["en"], "->", n, "matches,", t, "teams")
        total += n
    return total


def write_names():
    allnames = {c: n for c, n, _ in POOLS}
    allnames.update(WOMEN)
    for lang in ("ar", "en", "fr", "es", "tr"):
        p = os.path.join(LOCALES, lang + ".json")
        d = json.load(open(p, encoding="utf-8"))
        have = sum(1 for k in d if k.startswith("league."))
        for code, n in allnames.items():
            d["league." + code] = n[lang]
        json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(lang, "league.* keys before:", have, "after:", sum(1 for k in d if k.startswith("league.")))


def main(argv):
    if "--names" in argv:
        write_names()
        return 0
    res = RESERVE
    if "--reserve" in argv:
        res = int(argv[argv.index("--reserve") + 1])
    if "--load" not in argv:
        fetch("--active" in argv, res)
    load()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
