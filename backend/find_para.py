import re
import provider
KEYS = re.compile(r"deaf|blind|amput|para|cerebral|disab|special|ibsa|ifcpf|ifaf|deaflymp|paralymp|7-a-side|5-a-side|handisport", re.I)
c = provider.HighlightlyClient(reserve=10)
for ct in ["World", "Europe", "International", "Africa", "Asia", "South America", "North America", "Oceania"]:
    try:
        rows = c.leagues(ct)
    except Exception as e:
        print(ct, "error:", str(e)[:100]); continue
    hits = [r for r in rows if KEYS.search(r.get("name") or "")]
    print(ct, len(rows), "leagues,", len(hits), "matching")
    for r in hits:
        print("   ", r.get("id"), r.get("name"), [x.get("season") for x in (r.get("seasons") or [])][-3:])
print("remaining:", c.remaining)
