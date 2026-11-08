"""محرك التوقع الإحصائي لـ SiiMatchMind AI.

نموذج بواسون: لكل فريق قوة هجومية ودفاعية تُقدَّر من نتائجه السابقة،
مع وزن أكبر للمباريات الأحدث، وسحب القيم المتطرفة نحو المتوسط (shrinkage)
حتى لا تُبالَغ قوة فريق لعب مباريات قليلة.

بدون أي مكتبات خارجية (مكتبة بايثون القياسية فقط) ليعمل على Termux بسهولة.
"""
import math
from datetime import date

HALF_LIFE_DAYS = 365.0   # بعد 365 يومًا يصبح وزن المباراة النصف
SHRINK_K = 4.0           # قوة السحب نحو المتوسط (بوحدة الأهداف)
MAX_GOALS = 10           # أقصى أهداف في مصفوفة النتائج
LAM_MIN, LAM_MAX = 0.15, 4.5
DC_RHO = -0.15            # تصحيح Dixon-Coles للنتائج المنخفضة (0-0 و1-0 و0-1 و1-1)


def _d(s):
    return date.fromisoformat(s) if isinstance(s, str) else s


def played_matches(matches):
    return [m for m in matches if m.get("hg") is not None and m.get("ag") is not None]


class Model:
    """نموذج قوة الهجوم والدفاع (بواسون)."""

    def __init__(self, matches, as_of=None, half_life=HALF_LIFE_DAYS, k=SHRINK_K, iters=60):
        ms = played_matches(matches)
        if not ms:
            raise ValueError("لا توجد مباريات منتهية لتدريب النموذج")
        self.as_of = _d(as_of) if as_of else max(_d(m["date"]) for m in ms)
        self.teams = sorted({m["home"] for m in ms} | {m["away"] for m in ms})
        rows = {t: [] for t in self.teams}
        tw = hg = ag = 0.0
        for m in ms:
            age = max(0, (self.as_of - _d(m["date"])).days)
            w = 0.5 ** (age / half_life)
            tw += w
            hg += w * m["hg"]
            ag += w * m["ag"]
            rows[m["home"]].append((w, m["hg"], m["ag"], True, m["away"]))
            rows[m["away"]].append((w, m["ag"], m["hg"], False, m["home"]))
        self.mu_h = hg / tw
        self.mu_a = ag / tw
        self.n_matches = {t: len(r) for t, r in rows.items()}
        self.n_eff = {t: sum(x[0] for x in r) for t, r in rows.items()}
        att = {t: 1.0 for t in self.teams}
        dfn = {t: 1.0 for t in self.teams}
        for _ in range(iters):
            na, nd = {}, {}
            for t in self.teams:
                g = e = ga = ea = 0.0
                for w, gf, gc, is_home, opp in rows[t]:
                    mu_for = self.mu_h if is_home else self.mu_a
                    mu_against = self.mu_a if is_home else self.mu_h
                    g += w * gf
                    e += w * mu_for * dfn[opp]
                    ga += w * gc
                    ea += w * mu_against * att[opp]
                na[t] = (g + k) / (e + k)
                nd[t] = (ga + k) / (ea + k)
            att, dfn = na, nd
        self.att, self.dfn = att, dfn

    def lambdas(self, home, away):
        for t in (home, away):
            if t not in self.att:
                raise KeyError(t)
        lh = self.mu_h * self.att[home] * self.dfn[away]
        la = self.mu_a * self.att[away] * self.dfn[home]
        clip = lambda x: min(LAM_MAX, max(LAM_MIN, x))
        return clip(lh), clip(la)

    def predict(self, home, away):
        lh, la = self.lambdas(home, away)
        ph = [_pois(i, lh) for i in range(MAX_GOALS + 1)]
        pa = [_pois(j, la) for j in range(MAX_GOALS + 1)]
        mat = [[a * b for b in pa] for a in ph]
        mat[0][0] *= 1 - lh * la * DC_RHO
        mat[0][1] *= 1 + lh * DC_RHO
        mat[1][0] *= 1 + la * DC_RHO
        mat[1][1] *= 1 - DC_RHO
        s = sum(sum(r) for r in mat)
        mat = [[x / s for x in r] for r in mat]
        p_home = sum(mat[i][j] for i in range(MAX_GOALS + 1) for j in range(i))
        p_draw = sum(mat[i][i] for i in range(MAX_GOALS + 1))
        p_away = 1.0 - p_home - p_draw
        flat = sorted(((mat[i][j], i, j) for i in range(MAX_GOALS + 1) for j in range(MAX_GOALS + 1)), reverse=True)
        return {
            "lambda_home": lh,
            "lambda_away": la,
            "p_home": p_home,
            "p_draw": p_draw,
            "p_away": p_away,
            "top_scores": [{"score": f"{i}-{j}", "home": i, "away": j, "p": p} for p, i, j in flat[:5]],
            "most_likely": {"home": flat[0][1], "away": flat[0][2], "p": flat[0][0]},
            "p_over25": sum(mat[i][j] for i in range(MAX_GOALS + 1) for j in range(MAX_GOALS + 1) if i + j > 2),
            "p_btts": sum(mat[i][j] for i in range(1, MAX_GOALS + 1) for j in range(1, MAX_GOALS + 1)),
            "matrix": mat,
        }


def _pois(k, lam):
    return math.exp(-lam) * lam ** k / math.factorial(k)


def to_percent(probs):
    """يحوّل احتمالات إلى نسب صحيحة مجموعها 100 بالضبط (أكبر باقٍ)."""
    raw = [p * 100 for p in probs]
    base = [int(math.floor(x)) for x in raw]
    left = 100 - sum(base)
    order = sorted(range(len(raw)), key=lambda i: raw[i] - base[i], reverse=True)
    for i in order[:left]:
        base[i] += 1
    return base


# ---------- أدوات تحليل الفرق ----------

def team_results(matches, team, n=None, venue=None, before=None):
    """نتائج الفريق المنتهية، الأحدث أولًا."""
    out = []
    for m in played_matches(matches):
        if team not in (m["home"], m["away"]):
            continue
        if before and _d(m["date"]) >= _d(before):
            continue
        is_home = m["home"] == team
        if venue == "home" and not is_home or venue == "away" and is_home:
            continue
        gf, ga = (m["hg"], m["ag"]) if is_home else (m["ag"], m["hg"])
        out.append({
            "date": m["date"],
            "opponent": m["away"] if is_home else m["home"],
            "venue": "home" if is_home else "away",
            "gf": gf, "ga": ga,
            "result": "W" if gf > ga else ("D" if gf == ga else "L"),
        })
    out.sort(key=lambda r: r["date"], reverse=True)
    return out[:n] if n else out


def summarize(results):
    n = len(results)
    if n == 0:
        return {"played": 0, "w": 0, "d": 0, "l": 0, "gf": 0, "ga": 0,
                "avg_gf": None, "avg_ga": None, "clean_sheets": 0, "failed_to_score": 0, "points": 0}
    w = sum(r["result"] == "W" for r in results)
    d = sum(r["result"] == "D" for r in results)
    gf = sum(r["gf"] for r in results)
    ga = sum(r["ga"] for r in results)
    return {
        "played": n, "w": w, "d": d, "l": n - w - d, "gf": gf, "ga": ga,
        "avg_gf": round(gf / n, 2), "avg_ga": round(ga / n, 2),
        "clean_sheets": sum(r["ga"] == 0 for r in results),
        "failed_to_score": sum(r["gf"] == 0 for r in results),
        "points": 3 * w + d,
    }


def head_to_head(matches, a, b, n=10):
    out = []
    for m in played_matches(matches):
        if {m["home"], m["away"]} == {a, b}:
            out.append({"date": m["date"], "home": m["home"], "away": m["away"], "hg": m["hg"], "ag": m["ag"]})
    out.sort(key=lambda r: r["date"], reverse=True)
    out = out[:n]
    wa = sum((r["hg"] > r["ag"] and r["home"] == a) or (r["ag"] > r["hg"] and r["away"] == a) for r in out)
    wb = sum((r["hg"] > r["ag"] and r["home"] == b) or (r["ag"] > r["hg"] and r["away"] == b) for r in out)
    return {"matches": out, "count": len(out), "wins_a": wa, "wins_b": wb, "draws": len(out) - wa - wb}


def confidence(model, home, away, pred):
    """مستوى الثقة: كفاية البيانات + وضوح الفارق بين الاحتمالات. لا يتجاوز 0.85 أبدًا.
    المخرجات رموز (codes) تترجمها الواجهة إلى لغة المستخدم."""
    n = min(model.n_matches[home], model.n_matches[away])
    data_score = min(1.0, n / 20.0)
    probs = [pred["p_home"], pred["p_draw"], pred["p_away"]]
    ent = -sum(p * math.log(p) for p in probs if p > 0)
    clarity = 1 - ent / math.log(3)
    score = round(min(0.85, 0.6 * data_score + 0.4 * clarity), 2)
    level = "low" if score < 0.35 else ("mid" if score < 0.55 else "good")
    reasons = []
    if n < 8:
        reasons.append({"k": "few_matches", "n": n})
    if clarity < 0.1:
        reasons.append({"k": "close_probs"})
    return {"score": score, "level": level, "reasons": reasons}


def _rel(x):
    v = round((x - 1) * 100)
    return f"{'+' if v >= 0 else '-'}{abs(v)}%"


def team_stats_avg(dataset, team, n=10):
    """متوسط الاستحواذ والتسديدات والركنيات من آخر n مباريات تتوفر لها إحصائيات. None إن لم تتوفر."""
    stats = dataset.get("stats") or {}
    rows = []
    for m in sorted(played_matches(dataset["matches"]), key=lambda x: x["date"], reverse=True):
        if team in (m["home"], m["away"]) and m["id"] in stats and team in stats[m["id"]]:
            rows.append(stats[m["id"]][team])
        if len(rows) >= n:
            break
    if not rows:
        return None

    def avg(key):
        v = [r[key] for r in rows if r.get(key) is not None]
        return round(sum(v) / len(v), 1) if v else None
    return {"matches": len(rows), "possession": avg("possession"), "shots": avg("shots"),
            "shots_on": avg("shots_on"), "corners": avg("corners")}


def _with_history(matches, home, away):
    """يضيف مكتبة المواسم السابقة لتدريب النموذج فقط. لا يظهر منها شيء للمستخدم."""
    try:
        import history
        hist = history.matches_for(home, away)
        if hist:
            first = min((m["date"] for m in matches), default="9999")
            return [h for h in hist if h["date"] < first] + list(matches)
    except Exception:
        pass
    return matches


def build_analysis(dataset, home, away, n=10, as_of=None, match_id=None):
    """التحليل الكامل لمباراة بين فريقين. هذا ما تعيده واجهة /api/analyze (بدون نصوص مترجمة)."""
    names = {t["id"]: t["name"] for t in dataset["teams"]}
    if home not in names or away not in names:
        raise KeyError("unknown_team")
    if home == away:
        raise ValueError("same_team")
    matches = dataset["matches"]
    model = Model(_with_history(matches, home, away), as_of=as_of)
    pred = model.predict(home, away)
    pct = to_percent([pred["p_home"], pred["p_draw"], pred["p_away"]])
    conf = confidence(model, home, away, pred)

    hf = team_results(matches, home, n)
    af = team_results(matches, away, n)
    h_home = summarize(team_results(matches, home, n, venue="home"))
    a_away = summarize(team_results(matches, away, n, venue="away"))
    h2h = head_to_head(matches, home, away)
    hn, an = names[home], names[away]

    reasons = [
        {"k": "strength", "team": hn, "att": _rel(model.att[home]), "dfn": _rel(1 / model.dfn[home])},
        {"k": "strength", "team": an, "att": _rel(model.att[away]), "dfn": _rel(1 / model.dfn[away])},
        {"k": "home_adv", "mu_h": f"{model.mu_h:.2f}", "mu_a": f"{model.mu_a:.2f}"},
    ]
    if h_home["played"]:
        reasons.append({"k": "home_form", "team": hn, "w": h_home["w"], "d": h_home["d"], "l": h_home["l"], "n": h_home["played"]})
    if a_away["played"]:
        reasons.append({"k": "away_form", "team": an, "w": a_away["w"], "d": a_away["d"], "l": a_away["l"], "n": a_away["played"]})
    if h2h["count"]:
        reasons.append({"k": "h2h", "count": h2h["count"], "a": hn, "wa": h2h["wins_a"], "draws": h2h["draws"], "b": an, "wb": h2h["wins_b"]})

    st_h, st_a = team_stats_avg(dataset, home, n), team_stats_avg(dataset, away, n)
    missing = [{"k": "no_injury_model"}]
    if not st_h or not st_a:
        missing.append({"k": "no_stats"})
    if h2h["count"] < 3:
        missing.append({"k": "few_h2h"})
    ctx = None
    if match_id:
        ctx = (dataset.get("availability") or {}).get(match_id)
    if not ctx:
        missing.append({"k": "no_availability"})

    mp = pred["most_likely"]
    return {
        "home": {"id": home, "name": hn},
        "away": {"id": away, "name": an},
        "data_kind": dataset["meta"]["kind"],
        "prediction": {
            "percent": {"home": pct[0], "draw": pct[1], "away": pct[2]},
            "expected_goals": {"home": round(pred["lambda_home"], 2), "away": round(pred["lambda_away"], 2)},
            "most_likely_score": {"home": mp["home"], "away": mp["away"], "p": round(mp["p"], 4)},
            "top_scores": [{"score": s["score"], "p": round(s["p"], 4)} for s in pred["top_scores"]],
            "p_over25": round(pred["p_over25"], 4),
            "p_btts": round(pred["p_btts"], 4),
            "score_matrix": [[round(x, 4) for x in row[:6]] for row in pred["matrix"][:6]],
            "raw": {"home": pred["p_home"], "draw": pred["p_draw"], "away": pred["p_away"]},
        },
        "confidence": conf,
        "form": {"home": hf, "away": af},
        "form_summary": {"home": summarize(hf), "away": summarize(af)},
        "venue_split": {"home_at_home": h_home, "away_away": a_away},
        "head_to_head": h2h,
        "stats": {"home": st_h, "away": st_a} if (st_h or st_a) else None,
        "context": ctx,
        "reasons": reasons,
        "missing_data": missing,
    }


def standings(matches):
    """جدول ترتيب محسوب من النتائج المخزّنة لآخر موسم: النقاط ثم فارق الأهداف ثم الأهداف المسجلة.
    (قد يختلف عن الجدول الرسمي حيث تُستخدم معايير أخرى مثل المواجهات المباشرة.)"""
    played = played_matches(matches)
    if not played:
        return []
    latest = max(played, key=lambda m: (m["date"], m["id"]))
    season = latest.get("season")
    ms = sorted((m for m in played if m.get("season") == season), key=lambda m: (m["date"], m["id"]))
    rows = {}

    def row(t):
        return rows.setdefault(t, {"team": t, "p": 0, "w": 0, "d": 0, "l": 0, "gf": 0, "ga": 0, "form": []})

    for m in ms:
        for t, gf, ga in ((m["home"], m["hg"], m["ag"]), (m["away"], m["ag"], m["hg"])):
            r = row(t)
            r["p"] += 1
            r["gf"] += gf
            r["ga"] += ga
            res = "W" if gf > ga else ("D" if gf == ga else "L")
            r[{"W": "w", "D": "d", "L": "l"}[res]] += 1
            r["form"].append(res)
    out = []
    for r in rows.values():
        out.append({**r, "gd": r["gf"] - r["ga"], "pts": 3 * r["w"] + r["d"], "form": r["form"][-5:]})
    out.sort(key=lambda r: (-r["pts"], -r["gd"], -r["gf"], r["team"]))
    for i, r in enumerate(out, 1):
        r["pos"] = i
    return out
