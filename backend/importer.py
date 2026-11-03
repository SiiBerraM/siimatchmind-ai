"""استيراد بيانات حقيقية من API-Football إلى قاعدة البيانات.

مصدران: api-football (مواسم تاريخية 2022–2024 في الخطة المجانية، إحصائيات) وfootball-data (الموسم الحالي ومباريات اليوم، بدون إحصائيات).
يمكن الجمع بينهما في قاعدة واحدة: لكل بطولة مصدرها ونموذجها المستقل.
الدوريات العربية (الخطة المجانية لا توفر موسمها الحالي، فتُحلَّل بنتائج آخر موسم متاح):
    python importer.py --find egypt                      # يعرض رقم الدوري (طلب واحد)
    python importer.py --league 233 --season 2024        # مثال: الدوري المصري

football-data (بعد:  export FOOTBALL_DATA_KEY="مفتاحك"):
    python importer.py --source football-data --competition PL,PD,BL1,SA,FL1   # خمس بطولات (~35 ثانية بسبب حد 10 طلبات/دقيقة)

أمثلة api-football (بعد:  export API_FOOTBALL_KEY="مفتاحك"):
    python importer.py --league 39 --season 2023
    python importer.py --league 39 --season 2023 --stats-last 30
    python importer.py --league 39 --season 2024 --availability 5

كل طلب يستهلك من حصتك اليومية (الخطة المجانية 100 طلب يوميًا، ومواسمها محدودة).
--stats-last N : يجلب إحصائيات آخر N مباراة منتهية (طلب لكل مباراة).
--availability N : يجلب الإصابات والتشكيلات لأقرب N مباراة قادمة (طلبان لكل مباراة).
"""
import argparse
import time
import json
from datetime import date, datetime, timedelta, timezone

import db
import provider


def _ver():
    return str(time.time_ns())      # فريد دائمًا، فيُبطل ذاكرة الخدمة المؤقتة فورًا


def _stamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def wipe_data(con):
    """يمسح الفرق والمباريات والإحصائيات والتوفر فقط (لا يمس المستخدمين ولا المفضلة)."""
    for t in ("teams", "matches", "match_stats", "availability", "leagues"):
        con.execute(f"DELETE FROM {t}")
    con.execute("DELETE FROM kv WHERE k IN ('competitions', 'competition')")


def _save(rows, kind, leagues, season, replace=False):
    """leagues: قاموس {رمز البطولة: اسمها}."""
    """يحفظ المباريات والفرق. يرفض خلط مصدرين مختلفين إلا مع replace=True."""
    with db.connect() as con:
        if replace:                      # مسح صريح لكل البيانات (لا يمس الحسابات والمفضلة)
            wipe_data(con)
        teams = {}
        for m in rows:
            for t in m.pop("_teams"):
                tid, name, logo = (list(t) + [None])[:3]
                if tid not in teams or logo:
                    teams[tid] = (name, logo)
            con.execute(
                "INSERT INTO matches(id,date,time,round,season,league,home,away,hg,ag,status,source) VALUES(?,?,?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET date=excluded.date,time=excluded.time,round=excluded.round,league=excluded.league,"
                "hg=excluded.hg,ag=excluded.ag,status=excluded.status",
                (m["id"], m["date"], m["time"], m["round"], m["season"], m["league"], m["home"], m["away"], m["hg"], m["ag"], m["status"], kind))
        for tid, (name, logo) in teams.items():
            con.execute("INSERT INTO teams(id,name,source,logo) VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name, "
                        "logo=COALESCE(excluded.logo, teams.logo)", (tid, name, kind, logo))
        for code, name in leagues.items():
            con.execute("INSERT INTO leagues(code,name,source) VALUES(?,?,?) ON CONFLICT(code) DO UPDATE SET name=excluded.name", (code, name, kind))
        db.kv_set(con, "kind", kind)
        db.kv_set(con, "league", list(leagues.values())[-1])
        db.kv_set(con, "season", season)
        db.kv_set(con, "imported_at", _stamp())
        db.kv_set(con, "version", _ver())
    return len(rows), len(teams)


def run_fd(client, competition, season=None, replace=False, log=print):
    """استيراد من football-data.org: طلب واحد يجلب كل مباريات الموسم (الحالي إن لم تحدد موسمًا)."""
    data = client.matches(competition, season)
    name = (data.get("competition") or {}).get("name") or competition
    rows = [m for m in (provider.map_fd_match(x, competition) for x in data.get("matches", [])) if m]
    if not rows:
        raise provider.ProviderError("لم تُرجع الخدمة أي مباريات صالحة. تحقق من رمز البطولة (مثل PL) ومن صلاحية خطتك.")
    label = str((data.get("filters") or {}).get("season") or (rows[0]["season"] if rows else ""))
    n, t = _save(rows, "football-data", {competition: name}, label, replace)
    with db.connect() as con:
        known = [c for c in (db.kv_get(con, "competitions") or "").split(",") if c]
        if competition not in known:
            known.append(competition)
        db.kv_set(con, "competitions", ",".join(known))
    log(f"تم استيراد {n} مباراة و{t} فريقًا من football-data.org ({name}).")
    return {"matches": n, "teams": t, "requests": client.requests_made}


def run_hl(client, league_id, season, replace=False, log=print):
    """استيراد دوري من Highlightly (الموسم كاملًا): نحو 3–4 طلبات لكل دوري."""
    code = provider.hl_league_code(league_id)
    items, total = client.matches(league_id, season)
    rows = [m for m in (provider.map_hl_match(x, code) for x in items) if m]
    if not rows:
        raise provider.ProviderError("لم تُرجع الخدمة مباريات صالحة. تحقق من رقم الدوري والموسم، وقد تكون الخطة المجانية تخفي نتائج.")
    label = rows[0].get("_label") or code
    n, t = _save(rows, "highlightly", {code: label}, str(season), replace)
    with db.connect() as con:
        known = [c for c in (db.kv_get(con, "hl_leagues") or "").split(",") if c]
        key = f"{league_id}:{season}"
        if key not in known:
            known.append(key)
        db.kv_set(con, "hl_leagues", ",".join(known))
        db.kv_set(con, "last_refresh_hl", _stamp())
        if client.remaining is not None:
            db.kv_set(con, "requests_remaining_hl", client.remaining)
    log(f"{label}: استُوردت {n} مباراة صالحة من {total} (فرق: {t}). الخطة: {(client.plan or {}).get('tier')}. المتبقي اليوم: {client.remaining}")
    return {"league": code, "matches": n, "teams": t, "reported_total": total, "requests": client.requests_made}


def run_hl_stats(client, per_league=8, log=print):
    """يجلب إحصائيات آخر المباريات المنتهية التي ليس لها إحصائيات (طلب لكل مباراة). يتوقف عند اقتراب نفاد الحصة."""
    with db.connect() as con:
        todo = []
        for lg in [r["code"] for r in con.execute("SELECT code FROM leagues WHERE source='highlightly'")]:
            todo += [(r["id"], r["home"], r["away"]) for r in con.execute(
                "SELECT id, home, away FROM matches WHERE league=? AND status='played' "
                "AND id NOT IN (SELECT match_id FROM match_stats) AND id NOT IN (SELECT match_id FROM stats_tried) "
                "ORDER BY date DESC, id DESC LIMIT ?", (lg, per_league))]
    got = 0
    for mid, home, away in todo:
        try:
            detail = client.match_detail(mid[2:])
        except provider.BudgetExhausted:
            raise
        except provider.ProviderError as e:
            log(f"{mid}: {e}")
            continue
        stats = provider.map_hl_statistics(detail, {home, away})
        with db.connect() as con:
            for tid, st in stats.items():
                con.execute("INSERT OR REPLACE INTO match_stats(match_id,team_id,possession,shots,shots_on,corners) VALUES(?,?,?,?,?,?)",
                            (mid, tid, st["possession"], st["shots"], st["shots_on"], st["corners"]))
            if stats:
                db.kv_set(con, "version", _ver())
            else:
                con.execute("INSERT OR IGNORE INTO stats_tried(match_id) VALUES(?)", (mid,))      # لا إحصائيات لهذه المباراة؛ لا نعيد المحاولة
        got += 1 if stats else 0
    log(f"إحصائيات: {got} مباراة جديدة من {len(todo)} محاولة. المتبقي اليوم: {client.remaining}")
    return got


def run_hl_lineups(client, days=1, today=None, log=print):
    """يجلب التشكيلات المؤكدة لمباريات اليوم وغدًا (تظهر قبل المباراة بقليل، فما لم يُؤكَّد يُتجاهل)."""
    today = today or date.today()
    last = today + timedelta(days=days)
    with db.connect() as con:
        todo = [(r["id"], r["home"], r["away"]) for r in con.execute(
            "SELECT m.id, m.home, m.away FROM matches m JOIN leagues l ON l.code=m.league WHERE l.source='highlightly' "
            "AND m.status='scheduled' AND m.date>=? AND m.date<=? ORDER BY m.date, m.time", (today.isoformat(), last.isoformat()))]
    got = 0
    for mid, home, away in todo:
        try:
            raw = client.lineups(mid[2:])
        except provider.BudgetExhausted:
            raise
        except provider.ProviderError:
            continue                                                       # غالبًا لم تُؤكَّد التشكيلات بعد
        lineups = provider.map_hl_lineups(raw, home, away)
        if not lineups:
            continue
        with db.connect() as con:
            con.execute("INSERT OR REPLACE INTO availability(match_id,payload,fetched) VALUES(?,?,?)",
                        (mid, json.dumps({"injuries": [], "lineups": lineups}, ensure_ascii=False), _stamp()))
            db.kv_set(con, "version", _ver())
        got += 1
    log(f"تشكيلات: {got} مباراة من {len(todo)}. المتبقي اليوم: {client.remaining}")
    return got


def drop_league(code, log=print):
    """يحذف بطولة كاملة من قاعدة البيانات (مباريات وإحصائيات وتشكيلات وفرقها التي لا تلعب في بطولة أخرى). لا يمس الحسابات."""
    with db.connect() as con:
        ids = [r["id"] for r in con.execute("SELECT id FROM matches WHERE league=?", (code,))]
        if not ids and not con.execute("SELECT 1 FROM leagues WHERE code=?", (code,)).fetchone():
            raise provider.ProviderError(f"لا توجد بطولة بالرمز {code}")
        for i in range(0, len(ids), 500):
            chunk = ids[i:i + 500]
            marks = ",".join("?" * len(chunk))
            for table in ("match_stats", "availability", "stats_tried"):
                con.execute(f"DELETE FROM {table} WHERE match_id IN ({marks})", chunk)
        con.execute("DELETE FROM matches WHERE league=?", (code,))
        con.execute("DELETE FROM teams WHERE id NOT IN (SELECT home FROM matches UNION SELECT away FROM matches)")
        con.execute("DELETE FROM leagues WHERE code=?", (code,))
        comps = [c for c in (db.kv_get(con, "competitions") or "").split(",") if c and c != code]
        db.kv_set(con, "competitions", ",".join(comps))
        if code.startswith("hl"):
            hls = [c for c in (db.kv_get(con, "hl_leagues") or "").split(",") if c and not c.startswith(code[2:] + ":")]
            db.kv_set(con, "hl_leagues", ",".join(hls))
        db.kv_set(con, "version", _ver())
    log(f"حُذفت البطولة {code} ({len(ids)} مباراة).")
    return len(ids)


def find_hl_leagues(client, country, log=print):
    out = []
    for lg in client.leagues(country):
        seasons = sorted(s.get("season") for s in lg.get("seasons", []) if s.get("season"))
        out.append({"id": lg.get("id"), "name": lg.get("name"), "last_season": seasons[-1] if seasons else None})
        log(f"{lg.get('id')}  {lg.get('name')}  آخر موسم: {out[-1]['last_season']}")
    return out


def run(client, league, season, stats_last=0, availability=0, today=None, log=print, replace=False):
    today = today or date.today()
    summary = {"matches": 0, "teams": 0, "stats": 0, "availability": 0, "stopped": None}
    items = client.fixtures(league, season)
    rows = [m for m in (provider.map_fixture(i) for i in items) if m]
    if not rows:
        raise provider.ProviderError("لم تُرجع الخدمة أي مباريات صالحة. تحقق من رقم الدوري والموسم ومن صلاحية خطتك لهذا الموسم.")
    name = rows[0].get("_label") or rows[0]["league"]
    for m in rows:
        m["league"] = str(league)
    summary["matches"], summary["teams"] = _save(rows, "api-football", {str(league): name}, str(season), replace)
    log(f"تم استيراد {summary['matches']} مباراة و{summary['teams']} فريقًا.")

    try:
        if stats_last:
            with db.connect() as con:
                have = {r["match_id"] for r in con.execute("SELECT DISTINCT match_id FROM match_stats")}
                todo = [r["id"] for r in con.execute(
                    "SELECT id FROM matches WHERE status='played' ORDER BY date DESC, id DESC")if r["id"] not in have][:stats_last]
            for mid in todo:
                st = provider.map_statistics(client.statistics(mid[1:]))
                with db.connect() as con:
                    for tid, s in st.items():
                        con.execute("INSERT OR REPLACE INTO match_stats(match_id,team_id,possession,shots,shots_on,corners) VALUES(?,?,?,?,?,?)",
                                    (mid, tid, s["possession"], s["shots"], s["shots_on"], s["corners"]))
                    db.kv_set(con, "version", _ver())
                summary["stats"] += 1
        if availability:
            with db.connect() as con:
                soon = [r["id"] for r in con.execute(
                    "SELECT id FROM matches WHERE status='scheduled' AND date>=? ORDER BY date, time LIMIT ?",
                    (today.isoformat(), availability))]
            for mid in soon:
                payload = {"injuries": provider.map_injuries(client.injuries(mid[1:])),
                           "lineups": provider.map_lineups(client.lineups(mid[1:]))}
                with db.connect() as con:
                    con.execute("INSERT OR REPLACE INTO availability(match_id,payload,fetched) VALUES(?,?,?)",
                                (mid, json.dumps(payload, ensure_ascii=False), _stamp()))
                    db.kv_set(con, "version", _ver())
                summary["availability"] += 1
    except provider.BudgetExhausted as e:
        summary["stopped"] = str(e)
        log("توقف الاستيراد حفاظًا على الحصة: " + str(e))
    finally:
        with db.connect() as con:
            if client.remaining is not None:
                db.kv_set(con, "requests_remaining", client.remaining)
            db.kv_set(con, "requests_used_last_import", client.requests_made)
    return summary


def find_leagues(client, term, log=print):
    """يطبع أرقام الدوريات المطابقة (طلب واحد) لتعرف قيمة --league."""
    out = []
    for item in client.leagues(term):
        lg, ct = item.get("league") or {}, item.get("country") or {}
        years = sorted(s.get("year") for s in item.get("seasons", []) if s.get("year"))
        out.append({"id": lg.get("id"), "name": lg.get("name"), "country": ct.get("name"), "seasons": f"{years[0]}–{years[-1]}" if years else ""})
        log(f"{lg.get('id'):>5}  {lg.get('name')}  ({ct.get('name')})  المواسم: {out[-1]['seasons']}")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", choices=["api-football", "football-data", "highlightly"], default="api-football")
    ap.add_argument("--hl-league", help="highlightly: رقم أو عدة أرقام دوري مفصولة بفاصلة")
    ap.add_argument("--drop-league", help="احذف بطولة (أو عدة بطولات مفصولة بفاصلة) من قاعدة البيانات بالرمز الظاهر في /api/leagues، مثل 233")
    ap.add_argument("--hl-stats", type=int, default=0, help="highlightly: عدد المباريات المنتهية لكل دوري لجلب إحصائياتها (طلب لكل مباراة)")
    ap.add_argument("--hl-lineups", action="store_true", help="highlightly: جلب تشكيلات مباريات اليوم وغدًا")
    ap.add_argument("--hl-find", help="highlightly: ابحث عن أرقام دوريات دولة بالاسم الإنجليزي، مثل Egypt")
    ap.add_argument("--league", type=int, help="api-football: رقم الدوري")
    ap.add_argument("--season", type=int, help="api-football: الموسم (مطلوب) | football-data: اختياري، الافتراضي الموسم الحالي")
    ap.add_argument("--find", help="api-football: ابحث عن رقم دوري بالاسم، مثل saudi أو egypt أو morocco")
    ap.add_argument("--competition", help="football-data: رمز أو عدة رموز مفصولة بفاصلة، مثل PL,PD,BL1,SA,FL1")
    ap.add_argument("--stats-last", type=int, default=0)
    ap.add_argument("--availability", type=int, default=0)
    ap.add_argument("--reserve", type=int, default=10, help="عدد الطلبات المتبقية التي لا نتجاوزها (api-football)")
    ap.add_argument("--replace", action="store_true", help="امسح كل البيانات الحالية قبل الاستيراد (لا يمس الحسابات والمفضلة)")
    a = ap.parse_args()
    if a.drop_league:
        try:
            for c in (x.strip() for x in a.drop_league.split(",") if x.strip()):
                drop_league(c)
        except provider.ProviderError as e:
            raise SystemExit(f"خطأ: {e}")
        return
    try:
        if a.source == "highlightly":
            hc = provider.HighlightlyClient()
            if a.hl_find:
                find_hl_leagues(hc, a.hl_find)
            else:
                if not (a.hl_league or a.hl_stats or a.hl_lineups):
                    raise SystemExit("خطأ: highlightly يحتاج --hl-league مع --season، أو --hl-stats، أو --hl-lineups، أو --hl-find")
                if a.hl_league:
                    if a.season is None:
                        raise SystemExit("خطأ: أضف --season")
                    for i, lid in enumerate(x.strip() for x in a.hl_league.split(",") if x.strip()):
                        run_hl(hc, int(lid), a.season, a.replace and i == 0)
                if a.hl_stats:
                    run_hl_stats(hc, a.hl_stats)
                if a.hl_lineups:
                    run_hl_lineups(hc)
        elif a.source == "football-data":
            if not a.competition:
                raise SystemExit("خطأ: football-data يحتاج --competition مثل PL")
            client = provider.FootballDataClient()
            for i, comp in enumerate(c.strip().upper() for c in a.competition.split(",") if c.strip()):
                print(comp, "→", run_fd(client, comp, a.season, a.replace and i == 0))
        elif a.find:
            find_leagues(provider.Client(reserve=a.reserve), a.find)
        else:
            if a.league is None or a.season is None:
                raise SystemExit("خطأ: api-football يحتاج --league و--season")
            c = provider.Client(reserve=a.reserve)
            s = run(c, a.league, a.season, a.stats_last, a.availability, replace=a.replace)
            print("الملخص:", s, "| الطلبات المستخدمة:", c.requests_made, "| المتبقي اليوم:", c.remaining)
    except provider.ProviderError as e:
        raise SystemExit(f"خطأ: {e}")


if __name__ == "__main__":
    main()
