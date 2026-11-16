"""يجلب مواسم سابقة (2022–2024) للدوريات العربية من API-Football ويحفظها كملفات JSON في arabhist/.
لا يلمس قاعدة البيانات ولا يظهر شيء للمستخدم. نحو 15 طلبًا من حصة 100 يوميًا.
التشغيل:  python fetch_arab_history.py          (يتخطى الملفات الموجودة، فيمكن إعادته)
"""
import json
import os
import sys

import provider

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "arabhist")
# رمز الدوري في تطبيقك: رقم الدوري في API-Football
LEAGUES = {"hl199067": 233, "hl262041": 307, "hl170984": 200, "hl256935": 301, "hl260339": 305}
SEASONS = (2022, 2023, 2024)


def main():
    os.makedirs(OUT, exist_ok=True)
    client = provider.Client(reserve=10)
    used = 0
    for code, lid in LEAGUES.items():
        for season in SEASONS:
            path = os.path.join(OUT, "%s_%d.json" % (code, season))
            if os.path.exists(path):
                print("skip", code, season, "(exists)")
                continue
            try:
                r = client.fixtures(lid, season)
            except provider.BudgetExhausted as e:
                print("STOP: daily budget reached -", e, "| run again tomorrow")
                return 0
            except Exception as e:
                print("FAILED", code, season, str(e)[:120])
                continue
            used += 1
            items = r.get("response", []) if isinstance(r, dict) else (r or [])
            rows = []
            for it in items:
                try:
                    m = provider.map_fixture(it)
                except Exception:
                    continue
                if not m or m["status"] != "played":
                    continue
                (_, hn, _), (_, an, _) = m["_teams"]
                rows.append({"date": m["date"], "home": hn, "away": an, "hg": m["hg"], "ag": m["ag"]})
            rows.sort(key=lambda x: x["date"])
            json.dump(rows, open(path, "w", encoding="utf-8"), ensure_ascii=False)
            print("saved", code, season, len(rows), "played matches" + ("  <-- 0: check league id/season access" if not rows else ""))
    print("requests used:", used)
    return 0


if __name__ == "__main__":
    sys.exit(main())
