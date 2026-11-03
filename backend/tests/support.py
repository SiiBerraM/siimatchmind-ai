"""أدوات مشتركة للاختبارات: قاعدة بيانات مؤقتة وخادم محاكاة لـ API-Football بنفس بنية الاستجابات الموثّقة."""
import json
import os
import sys
import tempfile
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["SMM_PBKDF2_ITER"] = "1000"      # سريع في الاختبارات فقط


def fresh_db():
    os.environ["SMM_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")
    import service
    service._cache.clear()
    import api
    api._reset_limits()


class FakeFootballApi:
    """يحاكي /fixtures و/fixtures/statistics و/injuries و/fixtures/lineups. mode='errors' يحاكي خطأ الخطة."""

    def __init__(self, dataset, start_remaining=100, mode="ok"):
        self.ds, self.remaining, self.mode, self.calls, self.keys = dataset, start_remaining, mode, [], []
        self.fid_map = {}
        outer = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                u = urlparse(self.path)
                q = {k: v[0] for k, v in parse_qs(u.query).items()}
                outer.calls.append((u.path, q))
                outer.keys.append(self.headers.get("x-apisports-key"))
                outer.remaining -= 1
                resp = outer.build(u.path, q)
                data = json.dumps(resp).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("x-ratelimit-requests-remaining", str(outer.remaining))
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}"
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def close(self):
        self.srv.shutdown()
        self.srv.server_close()

    def _fixture(self, m):
        iso = datetime.fromisoformat(m["date"] + "T" + (m["time"] or "15:00") + ":00+00:00").isoformat()
        names = {t["id"]: t["name"] for t in self.ds["teams"]}
        played = m["status"] == "played"
        fid = int(m["id"].replace("s", "1").replace("r", "0").replace("m", "0"))
        self.fid_map[fid] = m
        return {
            "fixture": {"id": fid, "date": iso,
                        "status": {"short": "FT" if played else "NS"}},
            "league": {"id": 39, "name": "Test League", "country": "Egypt", "season": 2026, "round": f"Regular Season - {m['round']}"},
            "teams": {"home": {"id": int(m["home"][1:]), "name": names[m["home"]]},
                      "away": {"id": int(m["away"][1:]), "name": names[m["away"]]}},
            "goals": {"home": m["hg"], "away": m["ag"]},
        }

    def build(self, path, q):
        if self.mode == "errors":
            return {"errors": {"plan": "Free plans do not have access to this season"}, "response": []}
        if path == "/fixtures":
            items = [self._fixture(m) for m in self.ds["matches"]]
            items.append({**items[0], "fixture": {**items[0]["fixture"], "id": 999999, "status": {"short": "PST"}}})  # مؤجلة: تُتجاهل
            return {"errors": [], "response": items}
        if path == "/leagues":
            return {"errors": [], "response": [{"league": {"id": 233, "name": "Premier League", "type": "League"}, "country": {"name": "Egypt"},
                                                "seasons": [{"year": 2010}, {"year": 2024}]}]}
        fid = int(q["fixture"])
        m = self.fid_map[fid]
        h, a = int(m["home"][1:]), int(m["away"][1:])
        if path == "/fixtures/statistics":
            return {"errors": [], "response": [
                {"team": {"id": h}, "statistics": [{"type": "Ball Possession", "value": "55%"}, {"type": "Total Shots", "value": 14},
                                                   {"type": "Shots on Goal", "value": 5}, {"type": "Corner Kicks", "value": None}]},
                {"team": {"id": a}, "statistics": [{"type": "Ball Possession", "value": "45%"}, {"type": "Total Shots", "value": 9},
                                                   {"type": "Shots on Goal", "value": 3}, {"type": "Corner Kicks", "value": 4}]}]}
        if path == "/injuries":
            return {"errors": [], "response": [{"team": {"id": h}, "player": {"name": "لاعب 1", "reason": "Knee Injury"}}]}
        if path == "/fixtures/lineups":
            return {"errors": [], "response": [{"team": {"id": h}, "formation": "4-3-3",
                                                "startXI": [{"player": {"name": "حارس"}}, {"player": {"name": "مدافع"}}]}]}
        return {"errors": ["unknown"], "response": []}


class FakeFootballData:
    """يحاكي football-data.org v4: GET /competitions/{code}/matches (يتحقق من ترويسة X-Auth-Token)."""

    def __init__(self, dataset, key="fd-key", fail=None, datasets=None):
        self.ds, self.key, self.fail, self.calls = dataset, key, fail, []
        self.datasets = datasets or {}
        outer = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                u = urlparse(self.path)
                outer.calls.append((u.path, dict((k, v[0]) for k, v in parse_qs(u.query).items())))
                if outer.fail:
                    code, msg = outer.fail
                    return self._send(code, {"message": msg, "errorCode": code})
                if self.headers.get("X-Auth-Token") != outer.key:
                    return self._send(403, {"message": "The resource you are looking for is restricted.", "errorCode": 403})
                self._send(200, outer.build(u.path.split("/")[2]))

            def _send(self, code, obj):
                data = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}"
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def close(self):
        self.srv.shutdown()
        self.srv.server_close()

    NAMES = {"PL": "Premier League", "PD": "Primera Division", "BL1": "Bundesliga"}

    def build(self, code="PL"):
        ds = self.datasets.get(code, self.ds)
        base = 5000 + 10000 * (list(self.datasets).index(code) if code in self.datasets else 0)     # معرّفات المباريات فريدة بين البطولات كما في الخدمة الحقيقية
        names = {t["id"]: t["name"] for t in ds["teams"]}
        out = []
        for i, m in enumerate(ds["matches"]):
            played = m["status"] == "played"
            out.append({
                "id": base + i, "utcDate": m["date"] + "T" + (m["time"] or "15:00") + ":00Z",
                "status": "FINISHED" if played else ("TIMED" if i % 2 else "SCHEDULED"), "matchday": m["round"],
                "season": {"startDate": "2026-08-15"},
                "homeTeam": {"id": int(m["home"][1:]), "name": names[m["home"]] + " FC", "shortName": names[m["home"]], "crest": f"https://crests.example/{int(m['home'][1:])}.png"},
                "awayTeam": {"id": int(m["away"][1:]), "name": names[m["away"]] + " FC", "shortName": names[m["away"]], "crest": f"https://crests.example/{int(m['away'][1:])}.png"},
                "score": {"fullTime": {"home": m["hg"], "away": m["ag"]}},
            })
        out.append({**out[0], "id": base + 4999, "status": "POSTPONED"})       # مؤجلة: تُتجاهل
        out.append({**out[0], "id": base + 4998, "status": "IN_PLAY"})         # جارية: تُتجاهل
        out.append({**out[0], "id": base + 4997, "homeTeam": {"id": None, "name": "TBD"}, "status": "SCHEDULED"})   # فريق غير محدد: تُتجاهل
        return {"filters": {"season": "2026"}, "competition": {"name": self.NAMES.get(code, code), "code": code}, "matches": out}


class FakeHighlightly:
    """يحاكي Highlightly Football API كما في التوثيق: /leagues و/matches بصفحات limit/offset، وترويسة الحصة."""

    def __init__(self, dataset, key="hl-key", league_id=199067, season=2026, fail=None, start_remaining=100):
        self.ds, self.key, self.league_id, self.season, self.fail = dataset, key, league_id, season, fail
        self.remaining, self.calls = start_remaining, []
        outer = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                u = urlparse(self.path)
                q = {k: v[0] for k, v in parse_qs(u.query).items()}
                outer.calls.append((u.path, q))
                if outer.fail:
                    return self._send(outer.fail[0], {"message": outer.fail[1]})
                if self.headers.get("x-rapidapi-key") != outer.key:
                    return self._send(401, {"message": "Invalid API key"})
                outer.remaining -= 1
                self._send(200, outer.build(u.path, q), {"x-ratelimit-requests-remaining": str(outer.remaining), "x-ratelimit-requests-limit": "100"})

            def _send(self, code, obj, extra=None):
                data = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                for k, v in (extra or {}).items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(data)

        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}"
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def close(self):
        self.srv.shutdown()
        self.srv.server_close()

    def _all(self):
        names = {t["id"]: t["name"] for t in self.ds["teams"]}
        out = []
        for i, m in enumerate(self.ds["matches"]):
            played = m["status"] == "played"
            out.append({
                "id": 7000 + i, "round": f"Regular Season - {m['round']}",
                "date": m["date"] + "T" + (m["time"] or "15:00") + ":00.000Z",
                "country": {"code": "EG", "name": "Egypt", "logo": "x"},
                "homeTeam": {"id": int(m["home"][1:]), "name": names[m["home"]], "type": "club"},
                "awayTeam": {"id": int(m["away"][1:]), "name": names[m["away"]], "type": "club"},
                "league": {"id": self.league_id, "season": self.season, "name": "Premier League"},
                "state": {"description": "Finished" if played else "Not started",
                          "score": {"current": f"{m['hg']} - {m['ag']}" if played else None}},
            })
        base = out[0]
        for k, st in enumerate(("Postponed", "First half", "To be announced", "Cancelled")):     # حالات لا تدخل في النموذج
            out.append({**base, "id": 9000 + k, "state": {"description": st, "score": {"current": "1 - 0"}}})
        return out

    no_stats_ids = ()          # معرّفات مباريات بلا إحصائيات (للاختبار)

    def _detail(self, path):
        kind, mid = path.strip("/").split("/")
        i = int(mid) - 7000
        allm = self._all()
        m = allm[i]
        if kind == "matches":
            def team(t, poss):
                return {"team": {"id": t["id"], "logo": "x", "name": t["name"]}, "statistics": [
                    {"value": poss, "displayName": "Possession"}, {"value": 5, "displayName": "Shots on target"},
                    {"value": 4, "displayName": "Shots off target"}, {"value": 3, "displayName": "Blocked shots"},
                    {"value": 7, "displayName": "Corners"}, {"value": 0.42, "displayName": "Shots accuracy"}]}
            stats = [] if int(mid) in self.no_stats_ids else [team(m["homeTeam"], 0.57), team(m["awayTeam"], 0.43)]
            return [{**m, "statistics": stats, "events": []}]
        if m["state"]["description"] == "Not started" and i % 2 == 1:
            return {}                                                    # تشكيلات غير مؤكدة بعد
        line = lambda base: [[{"name": f"GK{base}", "number": 1, "position": "Goalkeeper", "id": base}],
                             [{"name": f"DF{base}", "number": 4, "position": "Defender", "id": base + 1}],
                             [{"name": f"FW{base}", "number": 9, "position": "Forward", "id": base + 2}]]
        return {"homeTeam": {"formation": "4-3-3", "substitutes": [], "initialLineup": line(100)},
                "awayTeam": {"formation": "4-4-2", "substitutes": [], "initialLineup": line(200)}}

    def build(self, path, q):
        limit, offset = int(q.get("limit", 100)), int(q.get("offset", 0))
        plan = {"tier": "BASIC", "message": "Some results might be hidden with FREE tier."}
        if path == "/leagues":
            rows = [{"id": self.league_id, "name": "Premier League", "seasons": [{"season": 2024}, {"season": 2026}, {"season": 2025}],
                     "country": {"code": "EG", "name": q.get("countryName", "Egypt")}},
                    {"id": 459473, "name": "Super Cup", "seasons": [{"season": 2025}], "country": {"code": "EG", "name": "Egypt"}}]
        elif path == "/matches":
            if int(q.get("leagueId", 0)) != self.league_id or int(q.get("season", 0)) != self.season:
                rows = []
            else:
                rows = self._all()
        elif path.startswith("/matches/") or path.startswith("/lineups/"):
            return self._detail(path)
        else:
            return {"message": "not found"}
        return {"data": rows[offset:offset + limit], "pagination": {"totalCount": len(rows), "offset": offset, "limit": limit}, "plan": plan}
