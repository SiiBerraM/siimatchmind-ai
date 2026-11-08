"""طبقة الخدمة: دوال بسيطة يستدعيها موجِّه الـ API ويستدعيها سكربت البناء الثابت.

مصدر البيانات: قاعدة البيانات إن كانت تحوي بيانات مستوردة من API-Football، وإلا البيانات التجريبية.
بنية القاموس الموحّدة:
{"meta": {"kind": ...}, "teams": [...], "matches": [...], "stats": {match_id: {team_id: {...}}}, "availability": {match_id: {...}}}
"""
import json
from datetime import date

import backtest
import db
import engine
import monitor
import provider
from demo_data import build_dataset

_cache = {}


def _load_real(con):
    today = date.today().isoformat()
    team_rows = [{"id": r["id"], "name": r["name"], "logo": r["logo"] or provider.default_logo(r["id"])}
                 for r in con.execute("SELECT id,name,logo FROM teams ORDER BY name")]
    matches = []
    for r in con.execute("SELECT * FROM matches ORDER BY date, time, id"):
        m = {k: r[k] for k in ("id", "date", "time", "round", "season", "league", "home", "away", "hg", "ag", "status")}
        if m["status"] == "scheduled":
            if m["date"] == today:
                m["status"] = "today"
            elif m["date"] < today:
                m["status"] = "unknown"      # مباراة قديمة لم تُحدَّث نتيجتها: أعد الاستيراد
        matches.append(m)
    last_league = {}
    for m in matches:
        last_league[m["home"]] = last_league[m["away"]] = m["league"] or ""
    teams = [{**t, "league": last_league.get(t["id"], "")} for t in team_rows]
    names = {r["code"]: r["name"] for r in con.execute("SELECT code,name FROM leagues")}
    sources = {r["code"]: r["source"] for r in con.execute("SELECT code,source FROM leagues")}
    default_src = db.kv_get(con, "kind")
    codes = sorted({t["league"] for t in teams if t["league"]}, key=lambda c: (c not in names, list(names).index(c) if c in names else 0, c))
    leagues = [{"code": c, "name": names.get(c, c), "source": sources.get(c, default_src)} for c in codes]
    stats = {}
    for r in con.execute("SELECT * FROM match_stats"):
        stats.setdefault(r["match_id"], {})[r["team_id"]] = {
            "possession": r["possession"], "shots": r["shots"], "shots_on": r["shots_on"], "corners": r["corners"]}
    avail = {r["match_id"]: json.loads(r["payload"]) | {"fetched": r["fetched"]} for r in con.execute("SELECT * FROM availability")}
    return {
        "meta": {"kind": db.kv_get(con, "kind"), "league": db.kv_get(con, "league"), "season": db.kv_get(con, "season"),
                 "imported_at": db.kv_get(con, "imported_at"), "leagues": leagues},
        "teams": teams, "matches": matches, "stats": stats, "availability": avail,
    }


def _demo():
    ds = build_dataset()
    for t in ds["teams"]:
        t["league"] = "DEMO"
        t["logo"] = None
    for m in ds["matches"]:
        m["league"] = "DEMO"
    ds["meta"]["leagues"] = [{"code": "DEMO", "name": "Demo League", "source": "demo"}]
    return {**ds, "stats": {}, "availability": {}}


def dataset():
    today = date.today().isoformat()
    with db.connect() as con:
        kind = db.kv_get(con, "kind")
        version = db.kv_get(con, "version", "")
        key = (today, kind, version, db.path())
        if _cache.get("key") != key:
            _cache.clear()
            _cache["key"] = key
            _cache["ds"] = _load_real(con) if kind and kind != "demo" else _demo()
    return _cache["ds"]


def _names(ds):
    return {t["id"]: t["name"] for t in ds["teams"]}


def _logos(ds):
    return {t["id"]: t.get("logo") for t in ds["teams"]}


def meta():
    ds = dataset()
    with db.connect() as con:
        stamps = [db.kv_get(con, k) for k in ("imported_at", "last_refresh", "last_refresh_hl")]
    return {**ds["meta"], "teams": len(ds["teams"]), "matches": len(ds["matches"]),
            "updated_at": max((s for s in stamps if s), default=None)}


def _norm_name(n):
    return " ".join((n or "").lower().replace("-", " ").replace("_", " ").split())


def leagues(include_hidden=False):
    """قائمة البطولات مرتبة أبجديًا. إن وُجدت نسخة أرشيفية (API-Football) لبطولة لها نسخة حالية بنفس الاسم فتُخفى."""
    ds = dataset()
    out = []
    for l in ds["meta"]["leagues"]:
        ms = [m for m in ds["matches"] if m["league"] == l["code"]]
        seasons = sorted({m["season"] for m in ms if m.get("season")})
        out.append({**l, "teams": sum(1 for t in ds["teams"] if t["league"] == l["code"]), "matches": len(ms),
                    "season": seasons[-1] if seasons else None,
                    "latest_date": max((m["date"] for m in ms if m["status"] == "played"), default=None),
                    "current": any(m["status"] in ("today", "scheduled") for m in ms)})
    if not include_hidden:
        by_name = {}
        for l in out:
            by_name.setdefault(_norm_name(l["name"]), []).append(l)
        hidden = {l["code"] for g in by_name.values() if len(g) > 1 and any(x["current"] for x in g)
                  for l in g if not l["current"] and l.get("source") == "api-football"}
        out = [l for l in out if l["code"] not in hidden]
    return sorted(out, key=lambda l: _norm_name(l["name"]))


def _league_ds(code):
    """مجموعة بيانات بطولة واحدة (النموذج يُدرَّب داخل البطولة فقط)."""
    ds = dataset()
    if code is None:
        return ds
    key = ("league", code)
    if key not in _cache:
        teams = [t for t in ds["teams"] if t["league"] == code]
        ids = {t["id"] for t in teams}
        _cache[key] = {**ds, "teams": teams, "matches": [m for m in ds["matches"] if m["league"] == code],
                       "stats": {k: v for k, v in ds["stats"].items() if any(t in ids for t in v)}}
    return _cache[key]


def _check_league(code):
    if code is not None and code not in {l["code"] for l in dataset()["meta"]["leagues"]}:
        raise KeyError("unknown_league")
    return code


def _team_league(team_id):
    t = next((t for t in dataset()["teams"] if t["id"] == team_id), None)
    if not t:
        raise KeyError(team_id)
    return t["league"]


def list_teams(q=None, league=None):
    _check_league(league)
    teams = _league_ds(league)["teams"]
    if q:
        q = q.strip()
        teams = [t for t in teams if q.lower() in t["name"].lower()]
    return teams


def _match_view(m, names, logos=None):
    logos = logos or {}
    return {**m, "home_name": names[m["home"]], "away_name": names[m["away"]],
            "home_logo": logos.get(m["home"]), "away_logo": logos.get(m["away"])}


def list_matches(kind, league=None, limit=16):
    _check_league(league)
    ds = _league_ds(league)
    names, logos = _names(dataset()), _logos(dataset())
    if kind == "today":
        sel = [m for m in ds["matches"] if m["status"] == "today"]
    elif kind == "upcoming":
        sel = [m for m in ds["matches"] if m["status"] == "scheduled"][:limit]
    elif kind == "results":
        sel = sorted((m for m in ds["matches"] if m["status"] == "played"),
                     key=lambda m: (m["date"], m["time"] or ""), reverse=True)[:limit]
    else:
        raise ValueError("bad_kind")
    return [_match_view(m, names, logos) for m in sel]


def team_detail(team_id):
    full = dataset()
    names, logos = _names(full), _logos(full)
    if team_id not in names:
        raise KeyError(team_id)
    ds = _league_ds(_team_league(team_id))
    ms = ds["matches"]
    res = engine.team_results(ms, team_id)
    upcoming = [m for m in ms if m["status"] in ("today", "scheduled") and team_id in (m["home"], m["away"])][:5]
    model = engine.Model(engine._with_history(ms, team_id, team_id))
    stats = engine.team_stats_avg(ds, team_id, 10)
    return {
        "team": {"id": team_id, "name": names[team_id], "logo": logos.get(team_id), "league": _team_league(team_id)},
        "data_kind": next((l.get("source") for l in full["meta"]["leagues"] if l["code"] == _team_league(team_id)), None) or full["meta"]["kind"],
        "summary": engine.summarize(res[:10]),
        "home": engine.summarize(engine.team_results(ms, team_id, 10, venue="home")),
        "away": engine.summarize(engine.team_results(ms, team_id, 10, venue="away")),
        "last_results": [{**r, "opponent_name": names[r["opponent"]], "opponent_logo": logos.get(r["opponent"])} for r in res[:10]],
        "upcoming": [_match_view(m, names, logos) for m in upcoming],
        "strength": {"attack": round(model.att[team_id], 2), "defense": round(1 / model.dfn[team_id], 2)},
        "stats": stats,
    }


def analyze(home, away, n=10, match_id=None, log=True):
    full = dataset()
    n = max(5, min(10, int(n)))
    lh, la = _team_league(home), _team_league(away)
    if lh != la:
        raise ValueError("different_leagues")
    ds = _league_ds(lh)
    res = engine.build_analysis(ds, home, away, n=n, match_id=match_id)
    import market
    market.blend_into(res, home, away)
    logos = _logos(full)
    res["home"]["logo"], res["away"]["logo"] = logos.get(home), logos.get(away)
    mm = next((x for x in ds["matches"] if x["id"] == match_id), None) if match_id else None
    res["match"] = ({k: mm[k] for k in ("id", "date", "time", "round", "status", "hg", "ag")}
                    if mm and {mm["home"], mm["away"]} == {home, away} else None)
    res["league"] = next((l for l in full["meta"]["leagues"] if l["code"] == lh), {"code": lh, "name": lh})
    res["data_kind"] = res["league"].get("source") or full["meta"]["kind"]
    if log and match_id:
        m = next((x for x in ds["matches"] if x["id"] == match_id), None)
        if m and m["status"] in ("scheduled", "today") and {m["home"], m["away"]} == {home, away}:
            monitor.log_prediction(match_id, home, away, res["prediction"]["raw"])
    return res


def quality(league=None):
    full = dataset()
    ls = full["meta"]["leagues"]
    if league is None and ls:
        league = ls[0]["code"]
    _check_league(league)
    key = ("quality", _cache.get("key"), league)
    if key not in _cache:
        res = backtest.run(_league_ds(league)["matches"])
        res["data_kind"] = next((l.get("source") for l in ls if l["code"] == league), None) or full["meta"]["kind"]
        res["league"] = league
        _cache[key] = res
    return _cache[key]


def standings_table(league=None):
    full = dataset()
    ls = full["meta"]["leagues"]
    if league is None and ls:
        league = sorted(ls, key=lambda l: _norm_name(l["name"]))[0]["code"]
    _check_league(league)
    names, logos = _names(full), _logos(full)
    rows = engine.standings(_league_ds(league)["matches"])
    return {"league": league, "rows": [{**r, "name": names[r["team"]], "logo": logos.get(r["team"])} for r in rows]}
