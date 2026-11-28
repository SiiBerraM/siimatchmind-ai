"""استيراد بيانات Sii-Football (رياضات ذوي الإعاقة) إلى قاعدة SiiMatchMind
دون المساس ببقية البيانات أو إعدادات التطبيق. التشغيل من مجلد backend:
    python import_sii_football.py
"""
import json
import re
import time
from datetime import datetime, timezone
from urllib.request import Request, urlopen

import db

BASE_URLS = [
    "https://siiberram.github.io/Sii-Football/api/para/",
    "https://siiberram.github.io/Sii-Football/api/",
]
SOURCE = "sii-football"
PARA_CATEGORIES = {"amputee-football", "blind-football", "cp-football"}

CATEGORY_LABELS = {
    "amputee-football": "Amputee Football (WAFF)",
    "blind-football": "Blind Football (IBSA)",
    "cp-football": "CP Football (IFCPF)",
}


def _get(filename):
    last_err = None
    for base in BASE_URLS:
        url = base + filename
        try:
            req = Request(url, headers={"User-Agent": "SiiMatchMind/1.0"})
            with urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as exc:
            last_err = exc
    raise RuntimeError(f"Failed to fetch {filename}: {last_err}")


def _slug(s):
    return re.sub(r"[^a-z0-9]+", "-", str(s or "").lower()).strip("-") or "unknown"


def _parse_date(val):
    if not val:
        return datetime.now(timezone.utc)
    s = str(val).strip()
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return datetime.now(timezone.utc)


def build(matches_doc, leagues_doc, teams_doc=None):
    rows, teams, leagues = [], {}, {}

    for comp in (leagues_doc.get("competitions") or []):
        cat = str(comp.get("category") or "").strip().lower()
        if cat not in PARA_CATEGORIES:
            continue
        code = "SF-" + _slug(cat)
        leagues[code] = CATEGORY_LABELS.get(cat, cat)

    for tm in ((teams_doc or {}).get("teams") or []):
        cat = str(tm.get("category") or "").strip().lower()
        name = str(tm.get("name") or "").strip()
        if cat in PARA_CATEGORIES and name:
            tid = f"sf:{cat}:{_slug(name)}"
            teams[tid] = name

    all_matches = list(matches_doc.get("matches") or [])
    if not all_matches:
        all_matches = list(leagues_doc.get("matches") or [])

    for idx, m in enumerate(all_matches, start=1):
        cat = str(m.get("category") or "").strip().lower()
        if cat not in PARA_CATEGORIES:
            continue

        raw_status = str(m.get("status") or "").strip().lower()
        if raw_status in ("finished", "played", "ft"):
            hg = m.get("home_score")
            ag = m.get("away_score")
            if hg is None or ag is None:
                continue
            status = "played"
        elif raw_status in ("scheduled", "upcoming", "fixture"):
            hg = ag = None
            status = "scheduled"
        else:
            continue

        home_name = m["home_team"]["name"] if isinstance(m.get("home_team"), dict) else str(m.get("home_team") or "").strip()
        away_name = m["away_team"]["name"] if isinstance(m.get("away_team"), dict) else str(m.get("away_team") or "").strip()
        if not home_name or not away_name:
            continue

        d = _parse_date(m.get("date_utc") or m.get("date") or m.get("fetched_at"))
        code = "SF-" + _slug(cat)
        hid = f"sf:{cat}:{_slug(home_name)}"
        aid = f"sf:{cat}:{_slug(away_name)}"
        mid = "sf-" + _slug(m.get("match_id") or f"{cat}-{idx}")

        rows.append({
            "id": mid,
            "date": d.date().isoformat(),
            "time": d.strftime("%H:%M"),
            "round": None,
            "season": str(d.year),
            "league": code,
            "home": hid,
            "away": aid,
            "hg": hg,
            "ag": ag,
            "status": status,
        })
        teams[hid] = home_name
        teams[aid] = away_name
        leagues.setdefault(code, CATEGORY_LABELS.get(cat, cat))

    return rows, teams, leagues


def save(rows, teams, leagues):
    with db.connect() as con:
        for r in rows:
            con.execute(
                "INSERT INTO matches(id,date,time,round,season,league,home,away,hg,ag,status,source) VALUES(?,?,?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET date=excluded.date,time=excluded.time,round=excluded.round,season=excluded.season,"
                "league=excluded.league,hg=excluded.hg,ag=excluded.ag,status=excluded.status",
                (r["id"], r["date"], r["time"], r["round"], r["season"], r["league"], r["home"], r["away"],
                 r["hg"], r["ag"], r["status"], SOURCE))
        for tid, name in teams.items():
            con.execute("INSERT INTO teams(id,name,source,logo) VALUES(?,?,?,NULL) "
                        "ON CONFLICT(id) DO UPDATE SET name=excluded.name", (tid, name, SOURCE))
        for code, name in leagues.items():
            con.execute("INSERT INTO leagues(code,name,source) VALUES(?,?,?) "
                        "ON CONFLICT(code) DO UPDATE SET name=excluded.name", (code, name, SOURCE))
        if rows:
            ids = [r["id"] for r in rows]
            con.execute(f"DELETE FROM matches WHERE source=? AND id NOT IN ({','.join('?' * len(ids))})", [SOURCE] + ids)
        db.kv_set(con, "version", str(time.time_ns()))


def main():
    matches_doc = _get("matches.json")
    leagues_doc = _get("leagues.json")
    try:
        teams_doc = _get("teams.json")
    except Exception:
        teams_doc = {}
    rows, teams, leagues = build(matches_doc, leagues_doc, teams_doc)
    if not rows and not teams and not leagues:
        print("لا توجد بيانات صالحة؛ لم يتغير شيء.")
        return
    save(rows, teams, leagues)
    print(f"تم: {len(rows)} مباراة، {len(teams)} فريقًا، {len(leagues)} بطولة (مصدر {SOURCE}).")


if __name__ == "__main__":
    main()
