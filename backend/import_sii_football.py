"""استيراد بيانات Sii-Football إلى قاعدة SiiMatchMind
دون المساس ببقية البيانات أو إعدادات التطبيق. التشغيل من مجلد backend:
    python import_sii_football.py
"""
import json
import os
import re
import time
from datetime import datetime, timezone
from urllib.request import Request, urlopen

import db

BASE_URLS = [
    "https://siiberram.github.io/Sii-Football/api/para/",
    "https://siiberram.github.io/Sii-Football/api/",
]

LOCAL_API_DIRS = [
    os.path.expanduser("~/Siifootball/Siifootball/api"),
    os.path.expanduser("~/sii/api"),
]

SOURCE = "sii-football"

CATEGORY_LABELS = {
    "amputee-football": "Amputee Football (WAFF)",
    "amputee": "Amputee Football (WAFF)",
    "blind-football": "Blind Football (IBSA)",
    "blind": "Blind Football (IBSA)",
    "cp-football": "CP Football (IFCPF)",
    "para": "Para / CP Football (IFCPF)",
    "deaf-football": "Deaf Football (ICSD / Deaflympics)",
    "deaf": "Deaf Football (ICSD / Deaflympics)",
    "powerchair-football": "Powerchair Football (FIPFA)",
    "powerchair": "Powerchair Football (FIPFA)",
    "short-stature-football": "Short Stature Football",
    "world-football": "World Football (Sii-Football)",
    "basketball": "Basketball (Sii-Football)",
    "motorsport": "Motorsport (Sii-Football)",
    "tennis": "Tennis (Sii-Football)",
    "volleyball": "Volleyball (Sii-Football)",
    "handball": "Handball (Sii-Football)",
    "multi-sport": "Multi-Sport (Sii-Football)",
}


def _slug(s):
    return re.sub(r"[^a-z0-9]+", "-", str(s or "").lower()).strip("-") or "unknown"


def _label_for_category(cat):
    c = str(cat or "").strip().lower()
    if not c:
        return "Sii-Football Category"
    if c in CATEGORY_LABELS:
        return CATEGORY_LABELS[c]
    return " ".join(part.capitalize() for part in c.replace("-", " ").split())


def _get(filename):
    # أولوية القراءة من الملفات المحلية المحدّثة إن وُجدت، ثم الروابط البعيدة
    for api_dir in LOCAL_API_DIRS:
        local_path = os.path.join(api_dir, filename)
        if os.path.isfile(local_path):
            try:
                with open(local_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass

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

    for comp in ((leagues_doc or {}).get("competitions") or []):
        cat = str(comp.get("category") or comp.get("sport") or "").strip().lower()
        comp_slug = _slug(comp.get("slug") or comp.get("code") or comp.get("name") or cat)
        if cat:
            cat_code = "SF-" + _slug(cat)
            leagues.setdefault(cat_code, _label_for_category(cat))
        if comp.get("name"):
            comp_code = "SF-" + comp_slug
            leagues.setdefault(comp_code, str(comp.get("name")).strip())

    for tm in ((teams_doc or {}).get("teams") or []):
        cat = str(tm.get("category") or tm.get("sport") or "general").strip().lower()
        name = str(tm.get("name") or "").strip()
        if name:
            tid = f"sf:{_slug(cat)}:{_slug(name)}"
            teams[tid] = name
            leagues.setdefault("SF-" + _slug(cat), _label_for_category(cat))

    all_matches = list((matches_doc or {}).get("matches") or [])
    if not all_matches:
        all_matches = list((leagues_doc or {}).get("matches") or [])

    for idx, m in enumerate(all_matches, start=1):
        cat = str(m.get("category") or m.get("sport") or "general").strip().lower()

        raw_status = str(m.get("status") or "").strip().lower()
        if raw_status in ("finished", "played", "ft", "completed"):
            hg = m.get("home_score")
            ag = m.get("away_score")
            if hg is None or ag is None:
                continue
            status = "played"
        elif raw_status in ("scheduled", "upcoming", "fixture", "not_started", "ns"):
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
        hid = f"sf:{_slug(cat)}:{_slug(home_name)}"
        aid = f"sf:{_slug(cat)}:{_slug(away_name)}"
        mid = "sf-" + _slug(m.get("match_id") or m.get("id") or f"{cat}-{idx}")

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
        leagues.setdefault(code, _label_for_category(cat))

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
