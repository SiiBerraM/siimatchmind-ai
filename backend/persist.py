"""لا تختفي بطولة بعد اليوم: كل ما يُستورد يُحفظ في backend/leaguedata/*.json داخل المستودع، ويُسترجع قبل كل بناء.
python persist.py restore              يسترجع كل البطولات المحفوظة إلى قاعدة البيانات (بلا طلبات)
python persist.py snapshot             يحفظ كل بطولات قاعدة بياناتك المحلية الحالية في الملفات
python persist.py refresh --max 14     يحدّث الأقدم تحديثًا فالأحدث من بطولات Highlightly ضمن حصة اليوم
"""
import glob
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone

B = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.join(B, "leaguedata")
SKIP = ("hlnat",)           # المنتخبات لها مجلدها (pooldata)
KEYS = ("id", "date", "time", "round", "season", "league", "home", "away", "hg", "ag", "status")


def _today():
    return datetime.now(timezone.utc).date().isoformat()


def _path(code):
    return os.path.join(DIR, code + ".json")


def _read(code):
    try:
        return json.load(open(_path(code), encoding="utf-8"))
    except Exception:
        return {}


def _plain(r):
    r = dict(r)
    if "_teams" in r:
        r["_teams"] = [list(t) for t in r["_teams"]]
    return r


def dump(rows, kind, leagues, season):
    by = {}
    for r in rows:
        by.setdefault(r.get("league"), []).append(r)
    cutoff = (datetime.now(timezone.utc).date() - timedelta(days=2)).isoformat()
    os.makedirs(DIR, exist_ok=True)
    for code, rs in by.items():
        if not code or str(code).startswith(SKIP) or not rs:
            continue
        old = _read(code)
        new_ids = {r["id"] for r in rs}
        merged = {r["id"]: r for r in old.get("rows", []) if r["id"] in new_ids or not (r.get("status") == "scheduled" and (r.get("date") or "") < cutoff)}
        for r in rs:
            merged[r["id"]] = _plain(r)
        data = {"code": code, "kind": kind, "label": (leagues or {}).get(code) or old.get("label") or code,
                "season": str(season or old.get("season") or ""), "refreshed": _today(),
                "rows": sorted(merged.values(), key=lambda r: ((r.get("date") or ""), r["id"]))}
        if old and old.get("rows") == data["rows"] and old.get("label") == data["label"] and old.get("season") == data["season"] and old.get("refreshed") == data["refreshed"]:
            continue
        json.dump(data, open(_path(code), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))


def restore():
    import importer
    save = getattr(importer, "_orig_save", importer._save)
    n = 0
    for path in sorted(glob.glob(os.path.join(DIR, "*.json"))):
        try:
            d = json.load(open(path, encoding="utf-8"))
        except Exception:
            continue
        rows = d.get("rows") or []
        if not rows:
            continue
        for r in rows:
            r["_teams"] = [tuple(t) for t in r.get("_teams", [])]
        save(rows, d.get("kind") or "highlightly", {d["code"]: d.get("label") or d["code"]}, d.get("season") or "", False)
        n += 1
        print("restored", d["code"], len(rows), "matches")
    print("restored leagues:", n)


def snapshot():
    import db
    with db.connect() as con:
        leagues = [dict(r) for r in con.execute("select * from leagues")]
        teams = {}
        for r in con.execute("select * from teams"):
            r = dict(r)
            teams[r.get("id")] = (r.get("id"), r.get("name"), r.get("logo"))
        ms = [dict(r) for r in con.execute("select * from matches")]
    if not ms:
        print("no matches in local database")
        return
    sample = ms[0]
    if any(k not in sample for k in ("id", "date", "home", "away", "league", "status")):
        print("unexpected matches columns:", sorted(sample), "- stopped, nothing written")
        return
    srcs = {l["code"]: (l.get("source") or "highlightly", l.get("name") or l["code"]) for l in leagues}
    by = {}
    for m in ms:
        row = {k: m.get(k) for k in KEYS}
        row["_teams"] = [teams.get(row["home"], (row["home"], row["home"], None)), teams.get(row["away"], (row["away"], row["away"], None))]
        by.setdefault(row["league"], []).append(row)
    for code, rows in sorted(by.items()):
        if str(code).startswith(SKIP):
            continue
        kind, label = srcs.get(code, ("highlightly", code))
        seasons = sorted({str(r.get("season") or "") for r in rows})
        dump(rows, kind, {code: label}, seasons[-1] if seasons else "")
        print("saved", code, len(rows), "matches |", label)


def refresh(max_n=14, reserve=25):
    import importer
    import provider
    client = provider.HighlightlyClient(reserve=reserve)
    files = []
    for path in glob.glob(os.path.join(DIR, "hl*.json")):
        try:
            d = json.load(open(path, encoding="utf-8"))
        except Exception:
            continue
        if d.get("kind") == "highlightly" and str(d["code"])[2:].isdigit() and not str(d["code"]).startswith(SKIP):
            files.append((d.get("refreshed") or "", d["code"], d.get("season")))
    files.sort()
    done = 0
    for _, code, season in files:
        if done >= max_n:
            break
        try:
            importer.run_hl(client, int(code[2:]), int(season) if str(season).isdigit() else season)
            done += 1
        except provider.BudgetExhausted as e:
            print("STOP: budget reached -", str(e)[:70])
            break
        except Exception as e:
            print("FAILED", code, str(e)[:80])
            done += 1
    print("refreshed leagues:", done)


def main(argv):
    if not argv or argv[0] not in ("restore", "snapshot", "refresh"):
        print(__doc__)
        return 1
    if argv[0] == "restore":
        restore()
    elif argv[0] == "snapshot":
        snapshot()
    else:
        opt = {argv[i]: argv[i + 1] for i in range(1, len(argv) - 1)}
        refresh(int(opt.get("--max", 14)), int(opt.get("--reserve", 25)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
