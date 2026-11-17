"""يجرّب معاملات النموذج (مدى تأثير المباريات القديمة half_life، وقوة التقليص k) بالاختبار التقدّمي
على مباريات لم يتدرّب عليها. لا يغيّر أي ملف: يطبع الجدول فقط.
التشغيل:  python tune_model.py            (الدوريات الافتراضية PL SA PD BL1)
خيارات:   --leagues PL,SA   --test 2425,2526   --step 14
"""
import math
import sys
import time
from collections import defaultdict

import engine
from engine import Model
from tune_market import MIN_TRAIN, days, load, outcome

EPS = 1e-12
HALF_LIVES = [120, 200, 300, 450, 700]
KS = [0.5, 1.5, 3, 6]


def run(data, tests, step, hl, k):
    rows = []
    for ms, by_date in data:
        tdates = sorted(d for d, v in by_date.items() if any(m["season"] in tests for m in v))
        mod = last = None
        for d in tdates:
            if mod is None or days(d, last) >= step:
                train = [m for m in ms if m["date"] < d]
                if len(train) < MIN_TRAIN:
                    continue
                mod, last = Model(train, as_of=d, half_life=hl, k=k), d
            for m in by_date[d]:
                if m["season"] not in tests or m["home"] not in mod.att or m["away"] not in mod.att:
                    continue
                p = mod.predict(m["home"], m["away"])
                rows.append(([p["p_home"], p["p_draw"], p["p_away"]], outcome(m)))
    return rows


def metrics(rows):
    n = len(rows)
    b = sum(sum((p[j] - (1 if j == o else 0)) ** 2 for j in range(3)) for p, o in rows) / n
    ll = -sum(math.log(max(EPS, p[o])) for p, o in rows) / n
    return b, ll, n


def main(argv):
    opt = {argv[i]: argv[i + 1] for i in range(len(argv) - 1) if argv[i].startswith("--")}
    leagues = opt.get("--leagues", "PL,SA,PD,BL1").split(",")
    tests = set("h" + s for s in opt.get("--test", "2425,2526").split(","))
    step = int(opt.get("--step", 14))
    data = []
    for code in leagues:
        ms, _ = load(code)
        by_date = defaultdict(list)
        for m in ms:
            by_date[m["date"]].append(m)
        data.append((ms, by_date))
    dh, dk = engine.HALF_LIFE_DAYS, engine.SHRINK_K
    combos = [(h, k) for h in HALF_LIVES for k in KS]
    if (dh, dk) not in combos:
        combos.append((dh, dk))
    print("leagues %s | test %s | retrain every %d days | %d combos" % (",".join(leagues), ",".join(sorted(tests)), step, len(combos)), file=sys.stderr)
    res, t0 = [], time.time()
    for i, (h, k) in enumerate(combos):
        b, ll, n = metrics(run(data, tests, step, h, k))
        res.append((ll, b, n, h, k))
        print("  %d/%d done (%ds)" % (i + 1, len(combos), time.time() - t0), file=sys.stderr)
    res.sort()
    print("matches per config: %d | current engine defaults: half_life=%s k=%s" % (res[0][2], dh, dk))
    print("rank  half_life  k     brier    logloss")
    for r, (ll, b, n, h, k) in enumerate(res[:8], 1):
        print("  %d    %-9s  %-4s  %.4f   %.4f%s" % (r, h, k, b, ll, "  <- current" if (h, k) == (dh, dk) else ""))
    cur = [x for x in res if (x[3], x[4]) == (dh, dk)][0]
    print("current: brier %.4f logloss %.4f | best: brier %.4f logloss %.4f | gain logloss %.4f" % (cur[1], cur[0], res[0][1], res[0][0], cur[0] - res[0][0]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
