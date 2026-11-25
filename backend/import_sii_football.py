"""استيراد بيانات Sii-Football (رياضات ذوي الإعاقة) إلى قاعدة SiiMatchMind
دون المساس ببقية البيانات أو إعدادات التطبيق. التشغيل من مجلد backend:
    python import_sii_football.py
"""
import json
import re
import time
from datetime import datetime
from urllib.request import Request, urlopen

import db

BASE = "https://siiberram.github.io/Sii-Football/data/"
SOURCE = "sii-football"


def _get(url):
    req = Request(url, headers={"User-Agent": "SiiMatchMind/1.0"})
    with urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def _slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def build(latest, comps):
    names = {c["code"]: c["name"] for c in comps}
    rows, teams, leagues = [], {}, {}
    for m in latest["matches"]:
        if m["status"] == "finished":
            hg, ag = m["home_team"]["score"], m["away_team"]["score"]
            if hg is None or ag is None:
                continue
            status = "played"
        elif m["status"] == "scheduled":
            hg = ag = None
            status = "scheduled"
        else:
            continue
        d = datetime.fromisoformat(m["date_utc"].replace("Z", "+00:00"))
        code = "SF-" + m["competition"]
        hid = f"sf:{m['sport']}:{_slug(m['home_team']['name'])}"
        aid = f"sf:{m['sport']}:{_slug(m['away_team']['name'])}"
        rows.append({"id": "sf" + m["match_id"], "date": d.date().isoformat(), "time": d.strftime("%H:%M"),
                     "round": None, "season": str(d.year), "league": code, "home": hid, "away": aid,
                     "hg": hg, "ag": ag, "status": status})
        teams[hid] = m["home_team"]["name"]
        teams[aid] = m["away_team"]["name"]
        leagues[code] = names.get(m["competition"], m["competition"])
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
    latest = _get(BASE + "latest.json")
    comps = _get(BASE + "api/v1/competitions.json")["data"]
    rows, teams, leagues = build(latest, comps)
    if not rows:
        print("لا توجد مباريات صالحة؛ لم يتغير شيء.")
        return
    save(rows, teams, leagues)
    print(f"تم: {len(rows)} مباراة، {len(teams)} فريقًا، {len(leagues)} بطولة (مصدر {SOURCE}).")


if __name__ == "__main__":
    main()
