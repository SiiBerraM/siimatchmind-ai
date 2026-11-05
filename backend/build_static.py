"""يولّد ملف frontend/data/static.json بنفس مخرجات واجهة API (للوضع الثابت بدون خادم)،
ويولّد اختياريًا نسخة HTML واحدة مستقلة:  python build_static.py --standalone
"""
import json
import sys
from pathlib import Path

import service

ROOT = Path(__file__).resolve().parent.parent
FRONT = ROOT / "docs"


def build():
    teams = service.list_teams()
    out = {
        "meta": service.meta(),
        "teams": teams,
        "leagues": service.leagues(),
        "standings": {l["code"]: service.standings_table(l["code"]) for l in service.leagues()},
        "matches": {k: service.list_matches(k) for k in ("today", "upcoming", "results")},
        "matches_by_league": {l["code"]: {k: service.list_matches(k, l["code"]) for k in ("today", "upcoming", "results")} for l in service.leagues()},
        "team_detail": {t["id"]: service.team_detail(t["id"]) for t in teams},
        "analyses": {},
        "quality": service.quality(),
    }
    seen = set()
    for m in out["matches"]["today"] + out["matches"]["upcoming"]:
        h, w = m["home"], m["away"]
        if (h, w) in seen:
            continue
        seen.add((h, w))
        try:
            out["analyses"][f"{h}|{w}"] = service.analyze(h, w, 10)
        except Exception:
            pass
    adir = FRONT / "data" / "analyses"
    adir.mkdir(parents=True, exist_ok=True)
    by_league = {}
    for t in teams:
        if t.get("league"):
            by_league.setdefault(t["league"], []).append(t["id"])
    for code, ids in by_league.items():
        pack = {}
        for h in ids:
            for w in ids:
                if h == w:
                    continue
                try:
                    pack[f"{h}|{w}"] = service.analyze(h, w, 10)
                except Exception:
                    pass
        (adir / (code + ".json")).write_text(json.dumps(pack, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print("league", code, len(pack), "analyses")
    p = FRONT / "data" / "static.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"تم: {p} ({p.stat().st_size / 1024:.0f} KB، {len(out['analyses'])} تحليلًا)")
    return out


def standalone():
    data = (FRONT / "data" / "static.json").read_text(encoding="utf-8")
    html = (FRONT / "index.html").read_text(encoding="utf-8")
    css = (FRONT / "style.css").read_text(encoding="utf-8")
    js = (FRONT / "app.js").read_text(encoding="utf-8")
    html = html.replace('<link rel="stylesheet" href="style.css">', f"<style>{css}</style>")
    for tag in ('<link rel="manifest" href="manifest.webmanifest">', '<link rel="icon" href="icons/icon-192.png">',
                '<link rel="apple-touch-icon" href="icons/icon-192.png">'):
        html = html.replace(tag, "")
    langs = (FRONT / "locales" / "languages.json").read_text(encoding="utf-8")
    locales = {l["code"]: json.loads((FRONT / "locales" / f"{l['code']}.json").read_text(encoding="utf-8")) for l in json.loads(langs)}
    inject = (f"window.SMM_STATIC={data};window.SMM_LANGS={langs};window.SMM_LOCALES={json.dumps(locales, ensure_ascii=False)};").replace("</", "<\\/")
    html = html.replace('<script src="app.js"></script>', f"<script>{inject}</script><script>{js}</script>")
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    (dist / "SiiMatchMind-standalone.html").write_text(html, encoding="utf-8")
    print("تم:", dist / "SiiMatchMind-standalone.html")


if __name__ == "__main__":
    build()
    if "--standalone" in sys.argv:
        standalone()
    if "--standalone" in sys.argv:
        standalone()
