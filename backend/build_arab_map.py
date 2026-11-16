"""يطابق أسماء فرق أرشيف API-Football (arabhist/) مع فرق الموسم الحالي (Highlightly) ويحفظ الجدول في team_map_arab.json.
يطبع ما تمت مطابقته بثقة ضعيفة وما لم يُطابق لنراجعه معًا. لا يغيّر قاعدة البيانات.
التشغيل:  python build_arab_map.py
"""
import difflib
import glob
import json
import os
import re
import sys

import service

B = os.path.dirname(os.path.abspath(__file__))
HIST = os.path.join(B, "arabhist")
OUT = os.path.join(B, "team_map_arab.json")
OVR = os.path.join(B, "team_map_arab_overrides.json")      # {"hl170984": {"اسم في الأرشيف": "معرّف الفريق الحالي"}} (اختياري)
STOP = {"fc", "sc", "cf", "cs", "fk", "ac", "club", "football", "fus", "sporting", "association", "athletic", "futbol"}
ALIAS = {"el": "al", "ahli": "ahly", "alahly": "al ahly", "alhilal": "al hilal"}
STRONG, WEAK = 0.84, 0.66


def tokens(s):
    s = re.sub(r"[^a-z0-9]+", " ", (s or "").lower().replace("é", "e").replace("’", "'"))
    out = []
    for t in s.split():
        t = ALIAS.get(t, t)
        if t not in STOP:
            out.extend(t.split())
    return out


def score(a, b):
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    ja, jb = "".join(sorted(ta)), "".join(sorted(tb))
    r = max(difflib.SequenceMatcher(None, " ".join(ta), " ".join(tb)).ratio(), difflib.SequenceMatcher(None, ja, jb).ratio())
    sa, sb = set(ta), set(tb)
    core_a = {t for t in sa if t != "al" and len(t) > 2}
    core_b = {t for t in sb if t != "al" and len(t) > 2}
    if core_a and core_b and (core_a <= core_b or core_b <= core_a):
        r = max(r, 0.9)
    return r


def main():
    cur = {}
    for t in service.list_teams():
        if str(t.get("league", "")).startswith("hl"):
            cur.setdefault(t["league"], []).append((t["id"], t.get("name") or ""))
    ovr = json.load(open(OVR, encoding="utf-8")) if os.path.exists(OVR) else {}
    result, report = {}, []
    for code, teams in sorted(cur.items()):
        names = set()
        for f in glob.glob(os.path.join(HIST, code + "_*.json")):
            for m in json.load(open(f, encoding="utf-8")):
                names.add(m["home"]); names.add(m["away"])
        if not names:
            continue
        pairs = sorted(((score(n, cn), n, tid, cn) for n in names for tid, cn in teams), reverse=True)
        used_n, used_t, mp = set(), set(), {}
        for n, tid in (ovr.get(code) or {}).items():
            mp[n] = tid; used_n.add(n); used_t.add(tid)
        for sc, n, tid, cn in pairs:
            if sc < WEAK or n in used_n or tid in used_t:
                continue
            mp[n] = tid; used_n.add(n); used_t.add(tid)
            if sc < STRONG:
                report.append("WEAK  %s  %.2f  archive='%s'  current='%s'" % (code, sc, n, cn))
        result[code] = mp
        miss = [cn for tid, cn in teams if tid not in used_t]
        print("%s: current teams %d | archive names %d | matched %d" % (code, len(teams), len(names), len(mp)))
        if miss:
            report.append("NO-MATCH %s current teams without archive twin: %s" % (code, " | ".join(miss)))
    json.dump(result, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print("\n".join(report) if report else "all matched confidently")
    return 0


if __name__ == "__main__":
    sys.exit(main())
