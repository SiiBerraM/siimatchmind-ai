"""يقيس هل تضيف مواسم 2022–2024 دقة لتوقعات الدوريات العربية، على مباريات الموسم الحالي فقط.
لكل مباراة حالية: نموذج (أ) مدرَّب على الأرشيف + مباريات الموسم قبلها، ونموذج (ب) على مباريات الموسم قبلها فقط.
التشغيل:  python arab_gain.py        (بعد patch_history.py)
"""
import math
import sys
from collections import defaultdict

import history
import service
from engine import Model

EPS = 1e-12
LEAGUES = ("hl199067", "hl262041", "hl170984", "hl256935", "hl260339")
NAMES = {"hl199067": "Egypt", "hl262041": "Saudi", "hl170984": "Morocco", "hl256935": "UAE", "hl260339": "Qatar"}
STEP, MIN_CUR, MIN_TEST_DATE_MATCHES = 7, 10, 10


def outcome(m):
    return 0 if m["hg"] > m["ag"] else (1 if m["hg"] == m["ag"] else 2)


def days(a, b):
    from datetime import date
    return (date.fromisoformat(a) - date.fromisoformat(b)).days


def metrics(rows):
    n = len(rows)
    if not n:
        return None
    b = sum(sum((p[k] - (1 if k == o else 0)) ** 2 for k in range(3)) for p, o in rows) / n
    ll = -sum(math.log(max(EPS, p[o])) for p, o in rows) / n
    return b, ll


def run(code):
    cur = sorted([m for m in service._league_ds(code)["matches"] if m["status"] == "played"], key=lambda m: (m["date"], m["id"]))
    hist = history.arab_matches(code)
    by_date = defaultdict(list)
    for m in cur:
        by_date[m["date"]].append(m)
    with_h, without_h = [], []
    ma = mb = None
    last = None
    for d in sorted(by_date):
        before = [m for m in cur if m["date"] < d]
        if len(before) < MIN_CUR:
            continue
        if last is None or days(d, last) >= STEP:
            ma, mb, last = Model(hist + before, as_of=d), Model(before, as_of=d), d
        for m in by_date[d]:
            h, a = m["home"], m["away"]
            if h not in ma.att or a not in ma.att or h not in mb.att or a not in mb.att:
                continue
            o = outcome(m)
            pa, pb = ma.predict(h, a), mb.predict(h, a)
            with_h.append(([pa["p_home"], pa["p_draw"], pa["p_away"]], o))
            without_h.append(([pb["p_home"], pb["p_draw"], pb["p_away"]], o))
    return with_h, without_h, len(hist)


def main():
    allw, allo = [], []
    print("league     test  hist | with-archive brier/logloss | season-only brier/logloss")
    for code in LEAGUES:
        try:
            w, o, nh = run(code)
        except Exception as e:
            print("%-9s FAILED %s" % (NAMES[code], str(e)[:80]))
            continue
        allw += w
        allo += o
        mw, mo = metrics(w), metrics(o)
        if mw:
            print("%-9s %4d %5d |   %.4f / %.4f        |   %.4f / %.4f" % (NAMES[code], len(w), nh, mw[0], mw[1], mo[0], mo[1]))
        else:
            print("%-9s no testable matches" % NAMES[code])
    mw, mo = metrics(allw), metrics(allo)
    if mw:
        print("ALL       %4d       |   %.4f / %.4f        |   %.4f / %.4f" % (len(allw), mw[0], mw[1], mo[0], mo[1]))
        print("uniform baseline: 0.6667 / 1.0986 | logloss gain from archive: %.4f" % (mo[1] - mw[1]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
