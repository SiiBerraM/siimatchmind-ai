import sys

P = "history.py"
s = open(P, encoding="utf-8").read()
if "_arab_ids" in s:
    print("already patched")
    sys.exit(0)

old = '''        if home in ids and away in ids:
            return _load().get(code, [])
    return []'''
new = '''        if home in ids and away in ids:
            return _load().get(code, [])
    for code, ids in _arab_ids().items():
        if home in ids and away in ids:
            return arab_matches(code)
    return []'''
assert s.count(old) == 1, "matches_for block not found exactly once"
s = s.replace(old, new)

s = s.rstrip("\n") + '''


# ---------- مواسم سابقة للدوريات العربية (API-Football 2022–2024) ----------
_arab_cache = None


def _arab():
    global _arab_cache
    if _arab_cache is not None:
        return _arab_cache
    out, ids = {}, {}
    try:
        tmap = json.load(open(os.path.join(B, "team_map_arab.json"), encoding="utf-8"))
    except Exception:
        tmap = {}
    for code, mp in tmap.items():
        ms = []
        for path in sorted(glob.glob(os.path.join(B, "arabhist", code + "_*.json"))):
            season = os.path.basename(path)[len(code) + 1:-5]
            try:
                rows = json.load(open(path, encoding="utf-8"))
            except Exception:
                continue
            for r in rows:
                try:
                    h = mp.get(r["home"]) or "ha_%s_%s" % (code, r["home"].replace(" ", "_"))
                    a = mp.get(r["away"]) or "ha_%s_%s" % (code, r["away"].replace(" ", "_"))
                    ms.append({"id": "ha%s_%s_%s_%s" % (season, code, r["date"], r["home"]), "date": r["date"],
                               "season": "ha" + season, "league": code, "home": h, "away": a,
                               "hg": int(r["hg"]), "ag": int(r["ag"]), "status": "played"})
                except Exception:
                    continue
        out[code] = ms
        ids[code] = set(mp.values())
    _arab_cache = (out, ids)
    return _arab_cache


def arab_matches(code):
    return _arab()[0].get(code, [])


def _arab_ids():
    return _arab()[1]
'''
open(P, "w", encoding="utf-8").write(s)
compile(s, P, "exec")
print("history.py patched OK")
