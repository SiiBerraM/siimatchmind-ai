"""مزج احتمالات السوق (أسعار المراهنات) مع توقع النموذج. إن تعذّر أي شيء يُترك النموذج كما هو."""
import csv
import io
import time
import urllib.request

import engine
import history

URL = "https://www.football-data.co.uk/fixtures.csv"
W_MARKET = 0.7          # وزن السوق في المزج
CACHE_SECONDS = 6 * 3600
COLS = (("PPH", "PPD", "PPA"), ("AvgH", "AvgD", "AvgA"), ("B365H", "B365D", "B365A"))
DIV = {"E0": "PL", "E1": "ELC", "D1": "BL1", "SP1": "PD", "I1": "SA", "F1": "FL1", "N1": "DED", "P1": "PPL"}

_cache = {"t": 0.0, "data": {}}


def _odds(r):
    for ks in COLS:
        try:
            q = [1 / float(r[k]) for k in ks]
            s = sum(q)
            return [x / s for x in q]
        except (KeyError, ValueError, ZeroDivisionError, TypeError):
            continue
    return None


def _fetch():
    if time.time() - _cache["t"] < CACHE_SECONDS:
        return _cache["data"]
    try:
        raw = urllib.request.urlopen(URL, timeout=8).read().decode("utf-8-sig")
        tm = history.team_map()
        data = {}
        for r in csv.DictReader(io.StringIO(raw)):
            code = DIV.get(r.get("Div"))
            if not code:
                continue
            mp = tm.get(code, {})
            h, a = mp.get(r["HomeTeam"]), mp.get(r["AwayTeam"])
            q = _odds(r)
            if h and a and q:
                data[(h, a)] = q
        _cache["t"], _cache["data"] = time.time(), data
    except Exception:
        _cache["t"] = time.time() - CACHE_SECONDS + 300   # أعد المحاولة بعد 5 دقائق
    return _cache["data"]


def blend_into(res, home, away):
    """يعدّل res["prediction"] في مكانه. يرجع True إن تم المزج."""
    try:
        q = _fetch().get((home, away))
        if not q:
            return False
        pr = res["prediction"]
        raw = pr["raw"]
        pm = [raw["home"], raw["draw"], raw["away"]]
        b = [W_MARKET * q[i] + (1 - W_MARKET) * pm[i] for i in range(3)]
        s = sum(b)
        b = [x / s for x in b]
        pr["model_raw"] = dict(raw)
        pr["raw"] = {"home": b[0], "draw": b[1], "away": b[2]}
        pc = engine.to_percent(b)
        pr["percent"] = {"home": pc[0], "draw": pc[1], "away": pc[2]}
        pr["market_blend"] = {"weight": W_MARKET,
                              "market": {"home": q[0], "draw": q[1], "away": q[2]}}
        return True
    except Exception:
        return False
