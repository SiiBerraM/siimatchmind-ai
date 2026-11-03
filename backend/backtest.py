"""اختبار رجعي (Walk-forward): لكل جولة يُدرَّب النموذج على ما قبلها فقط ثم يتوقع الجولة.

المقاييس: Brier Score وLog Loss والدقة وجدول المعايرة، مع مقارنة بخط أساس بسيط
(تكرار النتائج التاريخية: فوز/تعادل/خسارة).
"""
import math
from collections import defaultdict

from engine import Model, played_matches

EPS = 1e-12


def _outcome(m):
    return 0 if m["hg"] > m["ag"] else (1 if m["hg"] == m["ag"] else 2)


def _metrics(rows):
    n = len(rows)
    brier = sum(sum((p[k] - (1 if k == o else 0)) ** 2 for k in range(3)) for p, o in rows) / n
    logloss = -sum(math.log(max(EPS, p[o])) for p, o in rows) / n
    acc = sum(max(range(3), key=lambda k: p[k]) == o for p, o in rows) / n
    return {"brier": round(brier, 4), "log_loss": round(logloss, 4), "accuracy": round(acc, 4)}


def run(matches, min_train_rounds_matches=120, bins=5):
    ms = sorted(played_matches(matches), key=lambda m: (m["date"], m["id"]))
    by_date = defaultdict(list)
    for m in ms:
        by_date[m["date"]].append(m)
    dates = sorted(by_date)
    model_rows, base_rows = [], []
    calib = [[0, 0.0, 0.0] for _ in range(bins)]   # count, sum_pred, sum_obs
    seen = 0
    for d in dates:
        train = [m for m in ms if m["date"] < d]
        if len(train) >= min_train_rounds_matches:
            mod = Model(train, as_of=d)
            n = len(train)
            freq = [sum(_outcome(m) == k for m in train) / n for k in range(3)]
            for m in by_date[d]:
                if m["home"] not in mod.att or m["away"] not in mod.att:
                    continue
                p = mod.predict(m["home"], m["away"])
                probs = [p["p_home"], p["p_draw"], p["p_away"]]
                o = _outcome(m)
                model_rows.append((probs, o))
                base_rows.append((freq, o))
                for k in range(3):
                    b = min(bins - 1, int(probs[k] * bins))
                    calib[b][0] += 1
                    calib[b][1] += probs[k]
                    calib[b][2] += 1 if k == o else 0
        seen += len(by_date[d])
    if not model_rows:
        return {"available": False, "reason": "لا توجد مباريات كافية للاختبار الرجعي"}
    table = []
    ece = 0.0
    total = sum(c[0] for c in calib)
    for i, (c, sp, so) in enumerate(calib):
        if c:
            table.append({"range": f"{round(i * 100 / bins)}–{round((i + 1) * 100 / bins)}%",
                          "count": c, "predicted": round(sp / c, 3), "observed": round(so / c, 3)})
            ece += c / total * abs(sp / c - so / c)
    return {
        "available": True,
        "tested_matches": len(model_rows),
        "model": _metrics(model_rows),
        "baseline": _metrics(base_rows),
        "uniform_brier": round(2 / 3, 4),
        "calibration": table,
        "calibration_error": round(ece, 4),
    }
