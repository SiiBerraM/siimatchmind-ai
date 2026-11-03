"""بيانات تجريبية (DEMO) مولَّدة اصطناعيًا بذرة ثابتة.

تنبيه مهم: الفرق هنا خيالية والنتائج مولَّدة بالحاسوب، وليست بيانات حقيقية.
تُستخدم فقط لتجربة التطبيق وفحص خط التوقع إلى أن تُربط بيانات حقيقية.
"""
import math
import random
from datetime import date, timedelta

TEAM_NAMES = ["الصقور", "النمور", "الأسود", "العقبان", "الذئاب", "الفهود", "النسور", "الخيول",
              "القروش", "الجبال", "الواحة", "الشروق", "الميناء", "النخيل", "الريح", "البرق"]
KICKOFFS = ["15:00", "17:30", "19:00", "20:30", "21:45", "18:15", "16:00", "22:00"]
SEED = 20261012


def _poisson(rng, lam):
    L, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= L:
            return k
        k += 1


def _round_robin(ids):
    """جدول دوري من دورين بطريقة الدائرة. يعيد قائمة جولات، كل جولة قائمة (home, away)."""
    n = len(ids)
    arr = ids[:]
    first = []
    for r in range(n - 1):
        pairs = []
        for i in range(n // 2):
            a, b = arr[i], arr[n - 1 - i]
            pairs.append((a, b) if (r + i) % 2 == 0 else (b, a))
        first.append(pairs)
        arr = [arr[0]] + [arr[-1]] + arr[1:-1]
    second = [[(b, a) for a, b in rnd] for rnd in first]
    return first + second


def build_dataset(today=None):
    today = today or date.today()
    rng = random.Random(SEED)
    ids = [f"t{i + 1:02d}" for i in range(len(TEAM_NAMES))]
    teams = [{"id": i, "name": n} for i, n in zip(ids, TEAM_NAMES)]
    att = {i: math.exp(rng.gauss(0, 0.28)) for i in ids}
    dfn = {i: math.exp(rng.gauss(0, 0.28)) for i in ids}
    mu_h, mu_a = 1.50, 1.15

    matches = []
    n_rounds = 30
    played_rounds = 20            # الجولات 0..19 منتهية، الجولة 20 اليوم، والباقي قادمة
    for season, label in ((0, "الموسم السابق"), (1, "الموسم الحالي")):
        order = ids[:]
        rng.shuffle(order)
        schedule = _round_robin(order)
        for r, pairs in enumerate(schedule):
            if season == 0:
                day = today - timedelta(days=7 * (played_rounds + 1 + (n_rounds - r)) + 14)
                finished = True
            else:
                day = today + timedelta(days=7 * (r - played_rounds))
                finished = r < played_rounds
            for idx, (h, a) in enumerate(pairs):
                m = {
                    "id": f"s{season}r{r + 1:02d}m{idx + 1}",
                    "season": label, "round": r + 1, "date": day.isoformat(),
                    "time": KICKOFFS[idx % len(KICKOFFS)], "home": h, "away": a,
                    "hg": None, "ag": None,
                    "status": "played" if finished else ("today" if r == played_rounds else "scheduled"),
                }
                hg = _poisson(rng, mu_h * att[h] * dfn[a])
                ag = _poisson(rng, mu_a * att[a] * dfn[h])
                if finished:
                    m["hg"], m["ag"] = hg, ag
                matches.append(m)
        # انحراف بسيط في قوة الفرق بين الموسمين
        for i in ids:
            att[i] *= math.exp(rng.gauss(0, 0.08))
            dfn[i] *= math.exp(rng.gauss(0, 0.08))

    matches.sort(key=lambda m: (m["date"], m["time"], m["id"]))
    return {
        "meta": {
            "kind": "demo",
            "label": "بيانات تجريبية مولَّدة اصطناعيًا — فرق ونتائج خيالية",
            "generated_for": today.isoformat(),
        },
        "teams": teams,
        "matches": matches,
    }
