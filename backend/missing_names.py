import json
import os
import re

R = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs")
d = json.load(open(os.path.join(R, "data", "static.json"), encoding="utf-8"))
T = json.load(open(os.path.join(R, "locales", "teams.json"), encoding="utf-8"))
ar = json.load(open(os.path.join(R, "locales", "ar.json"), encoding="utf-8"))
SUF = re.compile(r"^(.+?) (Women|U17|U20|U21|U23)$")
known = lambda n: n in T or (SUF.match(n) and SUF.match(n).group(1) in T)
miss = sorted({t["name"] for t in d["teams"] if not known(t["name"])})
print("فرق بلا ترجمة: %d من %d" % (len(miss), len({t["name"] for t in d["teams"]})))
for n in miss:
    print("  ", n)
lm = [l["code"] + " | " + l["name"] for l in d["leagues"] if ("league." + l["code"]) not in ar and not re.search(r"[\u0600-\u06FF]", l["name"])]
print("بطولات بلا اسم عربي: %d" % len(lm))
for x in lm:
    print("  ", x)
