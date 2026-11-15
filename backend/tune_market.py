"""يضبط وزن السوق بالقياس على مواسم سابقة (اختبار تقدّمي Walk-forward).
التشغيل:  python tune_market.py PL        (أو أي دوري: ELC BL1 SA PD FL1 DED PPL)
خيارات:   --test 2425,2526,2627   المواسم المختبَرة   --step 7   أيام بين إعادة التدريب
"""
import csv
import glob
import math
import os
import sys
import time
from collections import defaultdict
from datetime import date

import history
import market
from engine import Model

EPS = 1e-12
MIN_TRAIN = 120


def outcome(m):
    return 0 if m["hg"] > m["ag"] else (1 if m["hg"] == m["ag"] else 2)


def load(code):
    fn = history.FILES[code]
    ms, odds = [], {}
    for path in sorted(glob.glob(os.path.join(history.DIR, fn + "_*.csv"))):
        season = os.path.basename(path)[len(fn) + 1:-4]
        try:
            rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
        except Exception:
            continue
        for r in rows:
            try:
                d = history._date(r["Date"])
                if not d or not r.get("FTHG") or not r.get("FTAG"):
                    continue
                mid = "h%s_%s_%s_%s" % (season, code, r["Date"], r["HomeTeam"])
                ms.append({"id": mid, "date": d, "season": "h" + season, "league": code,
                           "home": history._tid(r["HomeTeam"], code), "away": history._tid(r["AwayTeam"], code),
                           "hg": int(r["FTHG"]), "ag": int(r["FTAG"]), "status": "played"})
                q = market._odds(r)
                if q:
                    odds[mid] = q
            except Exception:
                continue
    ms.sort(key=lambda m: (m["date"], m["id"]))
    return ms, odds


def days(a, b):
    return (date.fromisoformat(a) - date.fromisoformat(b)).days


def score(rows, w):
    n = len(rows)
    b = ll = 0.0
    for pm, q, o in rows:
        p = [w * q[i] + (1 - w) * pm[i] for i in range(3)]
        s = sum(p)
        p = [x / s for x in p]
        b += sum((p[k] - (1 if k == o else 0)) ** 2 for k in range(3))
        ll += -math.log(max(EPS, p[o]))
    return b / n, ll / n


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    code = args[0] if args else "PL"
    opt = {argv[i]: argv[i + 1] for i in range(len(argv) - 1) if argv[i].startswith("--")}
    tests = set("h" + s for s in opt.get("--test", "2425,2526,2627").split(","))
    step = int(opt.get("--step", 7))
    if code not in history.FILES:
        print("unknown league:", code, "| available:", " ".join(history.FILES))
        return 1
    ms, odds = load(code)
    by_date = defaultdict(list)
    for m in ms:
        by_date[m["date"]].append(m)
    tdates = sorted(d for d, v in by_date.items() if any(m["season"] in tests for m in v))
    rows, mod, last, t0 = [], None, None, time.time()
    for i, d in enumerate(tdates):
        if mod is None or days(d, last) >= step:
            train = [m for m in ms if m["date"] < d]
            if len(train) < MIN_TRAIN:
                continue
            mod, last = Model(train, as_of=d), d
        for m in by_date[d]:
            if m["season"] not in tests or m["id"] not in odds:
                continue
            if m["home"] not in mod.att or m["away"] not in mod.att:
                continue
            p = mod.predict(m["home"], m["away"])
            rows.append(([p["p_home"], p["p_draw"], p["p_away"]], odds[m["id"]], outcome(m)))
        if i % 25 == 0:
            print("  %d/%d dates, %d matches, %ds" % (i, len(tdates), len(rows), time.time() - t0), file=sys.stderr)
    if not rows:
        print("no testable matches (need odds columns in the CSV files)")
        return 1
    print("league %s | test seasons %s | matches with odds: %d | retrain every %d days" % (code, ",".join(sorted(tests)), len(rows), step))
    print("uniform baseline: brier 0.6667  logloss 1.0986")
    print("w_market   brier    logloss")
    best = None
    for k in range(11):
        w = k / 10
        b, ll = score(rows, w)
        tag = " <- model only" if k == 0 else (" <- market only" if k == 10 else "")
        print("  %.1f     %.4f   %.4f%s" % (w, b, ll, tag))
        if best is None or ll < best[1]:
            best = (w, ll, b)
    print("best weight by logloss: %.1f (logloss %.4f, brier %.4f)" % best)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
