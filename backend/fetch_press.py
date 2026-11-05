import json, re, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

FEEDS = [
    ("en", "BBC Sport", "https://feeds.bbci.co.uk/sport/football/rss.xml"),
    ("en", "The Guardian", "https://www.theguardian.com/football/rss"),
    ("ar", "BBC Arabic", "https://feeds.bbci.co.uk/arabic/sports/rss.xml"),
    ("fr", "L'Equipe", "https://dwh.lequipe.fr/api/edito/rss?path=/Football/"),
    ("es", "Marca", "https://e00-marca.uecdn.es/rss/futbol/primera-division.xml"),
    ("tr", "TRT Haber", "https://www.trthaber.com/spor_articles.rss"),
    ("tr", "NTV Spor", "https://www.ntv.com.tr/spor.rss"),
]
KW = {
    "en": r"predict|preview|\btips?\b|odds|team news|line-?up",
    "ar": r"توقع|تشكيل|ترشيح|معاينة|مواجهة",
    "fr": r"pronostic|avant-match|compo|probable|présentation",
    "es": r"pronóstico|previa|alineaci|apuesta|posible",
    "tr": r"tahmin|muhtemel|ilk 11|ön izleme|iddaa",
}
OUT = Path(__file__).resolve().parent.parent / "docs" / "data" / "news.json"

def ts(s):
    try:
        return parsedate_to_datetime(s).astimezone(timezone.utc).isoformat()
    except Exception:
        return s or ""

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 SiiMatchMind"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read()

items = []
for lang, source, url in FEEDS:
    try:
        root = ET.fromstring(fetch(url))
        rows = root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry")
        ok = 0
        for it in rows:
            title = (it.findtext("title") or it.findtext("{http://www.w3.org/2005/Atom}title") or "").strip()
            link = (it.findtext("link") or "").strip()
            if not link:
                le = it.find("{http://www.w3.org/2005/Atom}link")
                link = le.get("href", "") if le is not None else ""
            if not title or not link.startswith("http"):
                continue
            pred = bool(re.search(KW[lang], title, re.I))
            date = ts(it.findtext("pubDate") or it.findtext("{http://www.w3.org/2005/Atom}updated") or "")
            items.append({"lang": lang, "source": source, "title": title, "link": link, "date": date, "pred": pred})
            ok += 1
            if ok >= 15:
                break
        print(f"{source}: {len(rows)} items, {ok} kept")
    except Exception as e:
        print(f"{source}: FAILED ({e})")

items.sort(key=lambda x: x["date"], reverse=True)
if items or not OUT.exists():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"updated": datetime.now(timezone.utc).isoformat(), "items": items[:120]}, ensure_ascii=False, indent=1), encoding="utf-8")
print("total:", len(items))
