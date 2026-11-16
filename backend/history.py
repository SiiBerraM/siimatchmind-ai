"""مكتبة المواسم السابقة لتدريب النموذج فقط (8 دوريات). لا تظهر للمستخدم."""
import csv
import glob
import json
import os
from datetime import datetime

B = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.join(B, "history")
FILES = {"PL": "E0", "ELC": "E1", "BL1": "D1", "PD": "SP1", "SA": "I1", "FL1": "F1", "DED": "N1", "PPL": "P1"}
_map = None
_all = None


def team_map():
    global _map
    if _map is None:
        try:
            _map = json.load(open(os.path.join(B, "team_map.json"), encoding="utf-8"))
        except Exception:
            _map = {}
    return _map


def _tid(name, code="PL"):
    return team_map().get(code, {}).get(name) or "h_%s_%s" % (code, name.replace(" ", "_"))


def _date(s):
    for f in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(s, f).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def _load():
    global _all
    if _all is not None:
        return _all
    out = {}
    for code, fn in FILES.items():
        ms = []
        for path in sorted(glob.glob(os.path.join(DIR, fn + "_*.csv"))):
            season = os.path.basename(path)[len(fn) + 1:-4]
            try:
                rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
            except Exception:
                continue
            for r in rows:
                try:
                    d = _date(r["Date"])
                    if not d or not r.get("FTHG") or not r.get("FTAG"):
                        continue
                    ms.append({"id": "h%s_%s_%s_%s" % (season, code, r["Date"], r["HomeTeam"]),
                               "date": d, "season": "h" + season, "league": code,
                               "home": _tid(r["HomeTeam"], code), "away": _tid(r["AwayTeam"], code),
                               "hg": int(r["FTHG"]), "ag": int(r["FTAG"]), "status": "played"})
                except Exception:
                    continue
        out[code] = ms
    _all = out
    return out


def matches(code=None):
    d = _load()
    if code:
        return d.get(code, [])
    return [m for v in d.values() for m in v]


def matches_for(home, away):
    """مباريات الدوري الذي ينتمي إليه الفريقان، أو قائمة فارغة."""
    for code, mp in team_map().items():
        ids = set(mp.values())
        if home in ids and away in ids:
            return _load().get(code, [])
    for code, ids in _arab_ids().items():
        if home in ids and away in ids:
            return arab_matches(code)
    return []


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
