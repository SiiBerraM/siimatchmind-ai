"""يفحص هل احتمالات نموذجك منحازة (خصوصًا التعادل وفوز المضيف)، ويجرّب تصحيحًا بسيطًا بمعاملين.
يُضبط التصحيح على موسم 2425 فقط، ثم يُقاس على مواسم لم تدخل في الضبط.
التشغيل:  python calib_check.py            (كل الدوريات الثمانية)   خيارات: --leagues PL,SA   --step 14
"""
import math
import sys
from collections import defaultdict

import history
from engine import Model
from tune_market import MIN_TRAIN, days, load, outcome

EPS = 1e-12
FIT, EVAL = "h2425", ("h2526", "h2627")


def collect(code, step):
    ms, _ = load(code)
    by_date = defaultdict(list)
    for m in ms:
        by_date[m["date"]].append(m)
    tdates = sorted(d for d, v in by_date.items() if any(m["season"] in (FIT,) + EVAL for m in v))
    rows, mod, last = [], None, None
    for d in tdates:
        if mod is None or days(d, last) >= step:
            train = [m for m in ms if m["date"] < d]
            if len(train) < MIN_TRAIN:
                continue
            mod, last = Model(train, as_of=d), d
        for m in by_date[d]:
            if m["season"] not in (FIT,) + EVAL or m["home"] not in mod.att or m["away"] not in mod.att:
                continue
            p = mod.predict(m["home"], m["away"])
            rows.append((m["season"], [p["p_home"], p["p_draw"], p["p_away"]], outcome(m)))
    return rows


def adj(p, hm, dm):
    q = [p[0] * hm, p[1] * dm, p[2]]
    s = sum(q)
    return [x / s for x in q]


def logloss(rows, hm=1.0, dm=1.0):
    return -sum(math.log(max(EPS, adj(p, hm, dm)[o])) for _, p, o in rows) / len(rows)


def main(argv):
    opt = {argv[i]: argv[i + 1] for i in range(len(argv) - 1) if argv[i].startswith("--")}
    leagues = opt.get("--leagues", ",".join(history.FILES)).split(",")
    step = int(opt.get("--step", 14))
    rows = []
    for c in leagues:
        r = collect(c, step)
        print("  %s: %d matches" % (c, len(r)), file=sys.stderr)
        rows += r
    fit = [x for x in rows if x[0] == FIT]
    ev = [x for x in rows if x[0] in EVAL]
    if not fit or not ev:
        print("not enough matches for fit/eval split")
        return 1
    print("matches: fit(%s)=%d eval=%d" % (FIT, len(fit), len(ev)))
    for name, part in (("fit", fit), ("eval", ev)):
        n = len(part)
        mp = [sum(p[k] for _, p, _ in part) / n for k in range(3)]
        ob = [sum(1 for _, _, o in part if o == k) / n for k in range(3)]
        print("%-4s predicted H/D/A: %.3f %.3f %.3f | observed: %.3f %.3f %.3f" % ((name,) + tuple(mp) + tuple(ob)))
    best = None
    for hm in (0.94, 0.97, 1.0, 1.03, 1.06):
        for dm in (0.9, 1.0, 1.1, 1.2, 1.3, 1.4):
            ll = logloss(fit, hm, dm)
            if best is None or ll < best[0]:
                best = (ll, hm, dm)
    _, hm, dm = best
    print("best correction fitted on %s: home x%.2f, draw x%.2f" % (FIT, hm, dm))
    print("eval logloss: before %.4f | after %.4f | gain %.4f" % (logloss(ev), logloss(ev, hm, dm), logloss(ev) - logloss(ev, hm, dm)))
    for s in EVAL:
        part = [x for x in rows if x[0] == s]
        if part:
            print("  season %s (%d): before %.4f after %.4f" % (s, len(part), logloss(part), logloss(part, hm, dm)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
