"""عميل API-Football (v3) بمكتبة urllib القياسية.

- المفتاح من متغير البيئة API_FOOTBALL_KEY على الخادم فقط، ولا يصل للواجهة أبدًا.
- يحترم الحصة: يتوقف عندما يقل الرصيد اليومي المتبقي عن `reserve`، ويفصل بين الطلبات زمنًا (حد الدقيقة).
- ملاحظة صدق: بنية الاستجابات هنا مبنية على توثيق API-Football v3، واختُبرت ضد خادم محاكاة محلي بنفس البنية،
  لكنها لم تُجرَّب بعد ضد الخدمة الحقيقية (لا مفتاح ولا إنترنت أثناء الإنشاء).
"""
import json
import os
import re
import time
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

PLAYED = {"FT", "AET", "PEN"}
SCHEDULED = {"NS", "TBD"}


class ProviderError(Exception):
    pass


def _check_key(key, name):
    """المفاتيح حروف وأرقام إنجليزية فقط؛ النص العربي (مثل: مفتاحك) يعني أن القيمة لم تُستبدل."""
    if not key.isascii() or any(c.isspace() for c in key):
        raise ProviderError(f"{name} يحوي حروفًا غير إنجليزية أو مسافات؛ يبدو أنك لم تستبدل العبارة العربية بمفتاحك الحقيقي.")
    return key


class BudgetExhausted(ProviderError):
    pass


class RateLimited(BudgetExhausted):
    """429 من المزوّد: نتوقف فورًا بدل المحاولة المتكررة."""


class Client:
    def __init__(self, key=None, base=None, reserve=10, min_interval=None, timeout=20):
        self.key = key or os.environ.get("API_FOOTBALL_KEY")
        if not self.key:
            raise ProviderError("متغير البيئة API_FOOTBALL_KEY غير مضبوط")
        _check_key(self.key, "API_FOOTBALL_KEY")
        self.base = (base or os.environ.get("API_FOOTBALL_BASE") or "https://v3.football.api-sports.io").rstrip("/")
        self.reserve = reserve
        self.min_interval = 6.5 if min_interval is None else min_interval   # الخطة المجانية: حد الدقيقة منخفض
        self.timeout = timeout
        self.remaining = None
        self.requests_made = 0
        self._last = 0.0

    def get(self, endpoint, **params):
        if self.remaining is not None and self.remaining <= self.reserve:
            raise BudgetExhausted(f"الرصيد اليومي المتبقي ({self.remaining}) وصل إلى الاحتياطي ({self.reserve})")
        wait = self.min_interval - (time.time() - self._last)
        if wait > 0:
            time.sleep(wait)
        url = f"{self.base}/{endpoint}" + (("?" + urlencode(params)) if params else "")
        req = Request(url, headers={"x-apisports-key": self.key, "Accept": "application/json"})
        try:
            with urlopen(req, timeout=self.timeout) as r:
                rem = r.headers.get("x-ratelimit-requests-remaining")
                data = json.loads(r.read().decode("utf-8"))
        except HTTPError as e:
            raise ProviderError(f"HTTP {e.code} من المزوّد") from None
        except URLError as e:
            raise ProviderError(f"تعذّر الاتصال بالمزوّد: {e.reason}") from None
        finally:
            self._last = time.time()
        self.requests_made += 1
        if rem is not None and str(rem).isdigit():
            self.remaining = int(rem)
        errs = data.get("errors")
        if errs:   # قد تكون قائمة أو قاموسًا
            raise ProviderError("خطأ من المزوّد: " + json.dumps(errs, ensure_ascii=False))
        return data.get("response") or []

    def leagues(self, search):
        return self.get("leagues", search=search)

    def fixtures(self, league, season):
        return self.get("fixtures", league=league, season=season)

    def statistics(self, fixture_id):
        return self.get("fixtures/statistics", fixture=fixture_id)

    def injuries(self, fixture_id):
        return self.get("injuries", fixture=fixture_id)

    def lineups(self, fixture_id):
        return self.get("fixtures/lineups", fixture=fixture_id)


# ---------- تحويل الاستجابات إلى بنية التطبيق ----------

def team_id(api_id):
    return f"a{api_id}"


def map_fixture(item):
    fx, lg, tm, gl = item["fixture"], item.get("league") or {}, item["teams"], item.get("goals") or {}
    short = (fx.get("status") or {}).get("short")
    if short in PLAYED:
        status = "played"
    elif short in SCHEDULED:
        status = "scheduled"
    else:
        return None      # مباراة جارية أو مؤجلة أو ملغاة: لا تدخل في التدريب ولا العرض
    if status == "played" and (gl.get("home") is None or gl.get("away") is None):
        return None
    d = datetime.fromisoformat(fx["date"].replace("Z", "+00:00"))
    rnd = re.search(r"(\d+)\s*$", lg.get("round") or "")
    return {
        "id": f"m{fx['id']}", "date": d.date().isoformat(), "time": d.strftime("%H:%M"),
        "round": int(rnd.group(1)) if rnd else None,
        "season": str(lg.get("season") or ""), "league": lg.get("name") or "",
        "_label": (f"{lg.get('name')} ({lg.get('country')})" if lg.get("country") else (lg.get("name") or "")),
        "home": team_id(tm["home"]["id"]), "away": team_id(tm["away"]["id"]),
        "hg": gl.get("home") if status == "played" else None,
        "ag": gl.get("away") if status == "played" else None,
        "status": status,
        "_teams": [(team_id(tm["home"]["id"]), tm["home"]["name"], tm["home"].get("logo")), (team_id(tm["away"]["id"]), tm["away"]["name"], tm["away"].get("logo"))],
    }


def _num(v):
    if v is None:
        return None
    if isinstance(v, str):
        v = v.strip().rstrip("%")
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def map_statistics(response):
    out = {}
    for block in response:
        s = {x.get("type"): x.get("value") for x in block.get("statistics", [])}
        shots, on, corners = _num(s.get("Total Shots")), _num(s.get("Shots on Goal")), _num(s.get("Corner Kicks"))
        out[team_id(block["team"]["id"])] = {
            "possession": _num(s.get("Ball Possession")),
            "shots": None if shots is None else int(shots),
            "shots_on": None if on is None else int(on),
            "corners": None if corners is None else int(corners),
        }
    return out


def map_injuries(response):
    return [{"team": team_id(i["team"]["id"]), "player": (i.get("player") or {}).get("name"),
             "reason": (i.get("player") or {}).get("reason") or (i.get("player") or {}).get("type")} for i in response]


def map_lineups(response):
    out = {}
    for L in response:
        out[team_id(L["team"]["id"])] = {
            "formation": L.get("formation"),
            "start": [(p.get("player") or {}).get("name") for p in L.get("startXI", [])],
        }
    return out


# ---------- football-data.org (الخطة المجانية: 12 بطولة، الموسم الحالي فقط، 10 طلبات/دقيقة، نتائج متأخرة قليلًا) ----------

FD_FINISHED = {"FINISHED"}
FD_SCHEDULED = {"SCHEDULED", "TIMED"}


class FootballDataClient:
    """يقرأ المفتاح من FOOTBALL_DATA_KEY (على الخادم فقط). بنية الاستجابة مبنية على توثيق v4، ومُختبَرة ضد خادم محاكاة فقط."""

    def __init__(self, key=None, base=None, min_interval=None, timeout=20):
        self.key = key or os.environ.get("FOOTBALL_DATA_KEY")
        if not self.key:
            raise ProviderError("متغير البيئة FOOTBALL_DATA_KEY غير مضبوط")
        _check_key(self.key, "FOOTBALL_DATA_KEY")
        self.base = (base or os.environ.get("FOOTBALL_DATA_BASE") or "https://api.football-data.org/v4").rstrip("/")
        self.min_interval = 6.5 if min_interval is None else min_interval   # 10 طلبات/دقيقة
        self.timeout = timeout
        self.requests_made = 0
        self.remaining = None
        self._last = 0.0

    def get(self, path, **params):
        wait = self.min_interval - (time.time() - self._last)
        if wait > 0:
            time.sleep(wait)
        params = {k: v for k, v in params.items() if v is not None}
        url = f"{self.base}/{path}" + (("?" + urlencode(params)) if params else "")
        req = Request(url, headers={"X-Auth-Token": self.key, "Accept": "application/json"})
        try:
            with urlopen(req, timeout=self.timeout) as r:
                data = json.loads(r.read().decode("utf-8"))
        except HTTPError as e:
            try:
                msg = json.loads(e.read().decode("utf-8")).get("message", "")
            except Exception:
                msg = ""
            raise ProviderError(f"HTTP {e.code} من football-data.org: {msg}".strip()) from None
        except URLError as e:
            raise ProviderError(f"تعذّر الاتصال بالمزوّد: {e.reason}") from None
        finally:
            self._last = time.time()
        self.requests_made += 1
        return data

    def matches(self, competition, season=None):
        return self.get(f"competitions/{competition}/matches", season=season)


def fd_team_id(api_id):
    return f"f{api_id}"


def map_fd_match(m, league_code=""):
    status = m.get("status")
    h, a = m.get("homeTeam") or {}, m.get("awayTeam") or {}
    if h.get("id") is None or a.get("id") is None:
        return None
    ft = ((m.get("score") or {}).get("fullTime")) or {}
    if status in FD_FINISHED:
        if ft.get("home") is None or ft.get("away") is None:
            return None
        st = "played"
    elif status in FD_SCHEDULED:
        st = "scheduled"
    else:
        return None
    d = datetime.fromisoformat(m["utcDate"].replace("Z", "+00:00"))
    return {
        "id": f"fm{m['id']}", "date": d.date().isoformat(), "time": d.strftime("%H:%M"),
        "round": m.get("matchday"), "season": str(((m.get("season") or {}).get("startDate") or "")[:4]), "league": league_code,
        "home": fd_team_id(h["id"]), "away": fd_team_id(a["id"]),
        "hg": ft.get("home") if st == "played" else None, "ag": ft.get("away") if st == "played" else None,
        "status": st,
        "_teams": [(fd_team_id(h["id"]), h.get("shortName") or h.get("name"), h.get("crest")), (fd_team_id(a["id"]), a.get("shortName") or a.get("name"), a.get("crest"))],
    }


# ---------- Highlightly (الخطة المجانية BASIC: 100 طلب/يوم، 100/دقيقة؛ تشمل الدوريات العربية للموسم الحالي) ----------
HL_FINISHED = {"Finished", "Finished after extra time", "Finished after penalties"}
HL_SCHEDULED = {"Not started"}


class HighlightlyClient:
    """يقرأ المفتاح من HIGHLIGHTLY_KEY (على الخادم فقط). الترويسة: x-rapidapi-key. بنية الاستجابة من توثيقهم الرسمي،
    ومُختبَرة ضد خادم محاكاة؛ أول تشغيل حقيقي هو أول اختبار فعلي للاستيراد الكامل."""

    def __init__(self, key=None, base=None, reserve=15, min_interval=None, timeout=20):
        self.key = key or os.environ.get("HIGHLIGHTLY_KEY")
        if not self.key:
            raise ProviderError("متغير البيئة HIGHLIGHTLY_KEY غير مضبوط")
        _check_key(self.key, "HIGHLIGHTLY_KEY")
        self.base = (base or os.environ.get("HIGHLIGHTLY_BASE") or "https://soccer.highlightly.net").rstrip("/")
        self.reserve = reserve
        self.min_interval = 0.8 if min_interval is None else min_interval
        self.timeout = timeout
        self.remaining = None
        self.requests_made = 0
        self.plan = None
        self._last = 0.0

    def get(self, path, **params):
        if self.remaining is not None and self.remaining <= self.reserve:
            raise BudgetExhausted(f"الرصيد اليومي المتبقي ({self.remaining}) وصل إلى الاحتياطي ({self.reserve})")
        wait = self.min_interval - (time.time() - self._last)
        if wait > 0:
            time.sleep(wait)
        params = {k: v for k, v in params.items() if v is not None}
        url = f"{self.base}{path}" + (("?" + urlencode(params)) if params else "")
        req = Request(url, headers={"x-rapidapi-key": self.key, "Accept": "application/json"})
        try:
            with urlopen(req, timeout=self.timeout) as r:
                rem = r.headers.get("x-ratelimit-requests-remaining")
                data = json.loads(r.read().decode("utf-8"))
        except HTTPError as e:
            try:
                msg = e.read().decode("utf-8")[:200]
            except Exception:
                msg = ""
            if e.code == 429:
                raise RateLimited(f"HTTP 429 من Highlightly: {msg}".strip()) from None
            raise ProviderError(f"HTTP {e.code} من Highlightly: {msg}".strip()) from None
        except URLError as e:
            raise ProviderError(f"تعذّر الاتصال بالمزوّد: {e.reason}") from None
        finally:
            self._last = time.time()
        self.requests_made += 1
        if rem is not None and str(rem).isdigit():
            self.remaining = int(rem)
        if isinstance(data, dict) and data.get("plan"):
            self.plan = data["plan"]
        return data

    def _paged(self, path, limit=100, **params):
        out, offset, total = [], 0, None
        while total is None or offset < total:
            page = self.get(path, limit=limit, offset=offset, **params)
            rows = page.get("data") or []
            total = (page.get("pagination") or {}).get("totalCount", len(rows))
            out.extend(rows)
            if not rows:
                break
            offset += limit
        return out, total

    def leagues(self, country_name):
        return self._paged("/leagues", countryName=country_name)[0]

    def matches(self, league_id, season):
        return self._paged("/matches", leagueId=league_id, season=season)

    def match_detail(self, match_id):
        """تفاصيل مباراة (إحصائيات وأحداث). الرد قائمة من عنصر واحد."""
        data = self.get(f"/matches/{match_id}")
        return (data[0] if data else {}) if isinstance(data, list) else (data or {})

    def lineups(self, match_id):
        return self.get(f"/lineups/{match_id}") or {}


def hl_team_id(i):
    return f"h{i}"


def hl_league_code(league_id):
    return f"hl{league_id}"


def map_hl_match(m, league_code):
    st = ((m.get("state") or {}).get("description")) or ""
    h, a = m.get("homeTeam") or {}, m.get("awayTeam") or {}
    if h.get("id") is None or a.get("id") is None or not m.get("date"):
        return None
    hg = ag = None
    if st in HL_FINISHED:
        cur = (((m.get("state") or {}).get("score")) or {}).get("current") or ""
        mm = re.match(r"^\s*(\d+)\s*-\s*(\d+)\s*$", cur)
        if not mm:
            return None
        hg, ag, status = int(mm.group(1)), int(mm.group(2)), "played"
    elif st in HL_SCHEDULED:
        status = "scheduled"
    else:
        return None           # مباشرة/مؤجلة/ملغاة/لم يُحدَّد موعدها/ممنوحة: لا تدخل
    d = datetime.fromisoformat(m["date"].replace("Z", "+00:00"))
    rnd = re.search(r"(\d+)\s*$", m.get("round") or "")
    lg = m.get("league") or {}
    return {
        "id": f"hm{m['id']}", "date": d.date().isoformat(), "time": d.strftime("%H:%M"),
        "round": int(rnd.group(1)) if rnd else None, "season": str(lg.get("season") or ""),
        "league": league_code, "home": hl_team_id(h["id"]), "away": hl_team_id(a["id"]),
        "hg": hg, "ag": ag, "status": status,
        "_teams": [(hl_team_id(h["id"]), h.get("name"), h.get("logo")), (hl_team_id(a["id"]), a.get("name"), a.get("logo"))],
        "_label": ((lg.get("name") or "") + (f" ({(m.get('country') or {}).get('name')})" if (m.get("country") or {}).get("name") else "")),
    }


def _hl_stat_map(entry):
    return {(s.get("displayName") or "").strip().lower(): s.get("value") for s in (entry.get("statistics") or [])}


def map_hl_statistics(detail, team_ids):
    """يحوّل إحصائيات Highlightly إلى {team_id: {possession, shots, shots_on, corners}}.
    الاستحواذ يأتي كنسبة (0.57)، وإجمالي التسديدات = على المرمى + خارجه + محجوبة (تحققتُ أنه يطابق «دقة التسديد» في رد حقيقي)."""
    out = {}
    for entry in detail.get("statistics") or []:
        tid = hl_team_id((entry.get("team") or {}).get("id"))
        if tid not in team_ids:
            continue
        s = _hl_stat_map(entry)
        pos = s.get("possession")
        if isinstance(pos, (int, float)):
            pos = round(pos * 100, 1) if pos <= 1 else round(float(pos), 1)
        else:
            pos = None
        on, off, blk = s.get("shots on target"), s.get("shots off target"), s.get("blocked shots")
        total = s.get("total shots") if isinstance(s.get("total shots"), (int, float)) else s.get("shots")
        if not isinstance(total, (int, float)):
            total = (on + off + blk) if all(isinstance(v, (int, float)) for v in (on, off, blk)) else None
        corners = s.get("corners")
        if pos is None and total is None and not isinstance(corners, (int, float)):
            continue
        out[tid] = {"possession": pos, "shots": None if total is None else int(total),
                    "shots_on": int(on) if isinstance(on, (int, float)) else None,
                    "corners": int(corners) if isinstance(corners, (int, float)) else None}
    return out


def map_hl_lineups(raw, home_id, away_id):
    """{team_id: {formation, start: [أسماء الأساسيين]}} من رد /lineups."""
    out = {}
    for side, tid in (("homeTeam", home_id), ("awayTeam", away_id)):
        t = (raw or {}).get(side) or {}
        rows = t.get("initialLineup") or []
        names = [p.get("name") for row in rows for p in (row or []) if p.get("name")]
        if names:
            out[tid] = {"formation": t.get("formation"), "start": names}
    return out


def default_logo(team_id):
    """شعار احتياطي من نمط روابط المزوّد، إن لم يُخزَّن شعار صريح (الواجهة تعرض حرفًا بديلًا إن فشل التحميل)."""
    kind, num = (team_id or " ")[0], (team_id or "")[1:]
    if not num.isdigit():
        return None
    return {"h": f"https://highlightly.net/soccer/images/teams/{num}.png",
            "f": f"https://crests.football-data.org/{num}.png",
            "a": f"https://media.api-sports.io/football/teams/{num}.png"}.get(kind)
