"""اختبارات الحسابات والـ API والاستيراد والمراقبة وخادم HTTP الحقيقي. التشغيل من backend:
    python -m unittest discover -s tests -v
"""
import json
import os
import sys
import threading
import unittest
import urllib.error
import urllib.request
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(__file__))
from support import FakeFootballApi, FakeFootballData, FakeHighlightly, fresh_db      # noqa: E402

import accounts      # noqa: E402
import accounts as accounts_mod  # noqa: E402
import api           # noqa: E402
import autorefresh   # noqa: E402
import backup        # noqa: E402
import db            # noqa: E402
import importer      # noqa: E402
import monitor       # noqa: E402
import provider      # noqa: E402
import service       # noqa: E402
from demo_data import build_dataset   # noqa: E402


class AccountTests(unittest.TestCase):
    def setUp(self):
        fresh_db()

    def test_register_login_logout(self):
        r = accounts.register("A@Example.com", "password123")
        self.assertEqual(r["user"]["email"], "a@example.com")
        self.assertEqual(accounts.user_from_token(r["token"])["email"], "a@example.com")
        l = accounts.login("a@example.com", "password123")
        accounts.logout(l["token"])
        self.assertIsNone(accounts.user_from_token(l["token"]))
        self.assertIsNotNone(accounts.user_from_token(r["token"]))

    def test_validation_and_duplicates(self):
        for bad, code in (("not-an-email", "invalid_email"),):
            with self.assertRaises(accounts.AuthError) as c:
                accounts.register(bad, "password123")
            self.assertEqual(c.exception.code, code)
        with self.assertRaises(accounts.AuthError) as c:
            accounts.register("b@example.com", "short")
        self.assertEqual(c.exception.code, "weak_password")
        accounts.register("b@example.com", "password123")
        with self.assertRaises(accounts.AuthError) as c:
            accounts.register("B@example.com", "password123")
        self.assertEqual(c.exception.status, 409)

    def test_password_not_stored_plain_and_lockout(self):
        accounts.register("c@example.com", "password123")
        with db.connect() as con:
            h = con.execute("SELECT pw_hash FROM users").fetchone()["pw_hash"]
        self.assertNotIn("password123", h)
        self.assertTrue(h.startswith("pbkdf2$"))
        for _ in range(5):
            with self.assertRaises(accounts.AuthError) as c:
                accounts.login("c@example.com", "wrong-password")
            self.assertEqual(c.exception.status, 401)
        with self.assertRaises(accounts.AuthError) as c:
            accounts.login("c@example.com", "password123")      # حتى الصحيحة مقفلة مؤقتًا
        self.assertEqual(c.exception.status, 429)

    def test_token_stored_hashed_and_expiry(self):
        r = accounts.register("d@example.com", "password123")
        with db.connect() as con:
            self.assertIsNone(con.execute("SELECT 1 FROM sessions WHERE token_hash=?", (r["token"],)).fetchone())
            con.execute("UPDATE sessions SET expires='2000-01-01T00:00:00+00:00'")
        self.assertIsNone(accounts.user_from_token(r["token"]))

    def test_favorites_history(self):
        uid = accounts.register("e@example.com", "password123")["user"]["id"]
        accounts.fav_add(uid, "t01", "t02"); accounts.fav_add(uid, "t01", "t02")
        self.assertEqual(accounts.fav_list(uid), [{"home": "t01", "away": "t02"}])
        accounts.fav_remove(uid, "t01", "t02")
        self.assertEqual(accounts.fav_list(uid), [])
        accounts.hist_add(uid, "t01", "t02", [50, 30, 20]); accounts.hist_add(uid, "t01", "t02", [40, 30, 30])
        h = accounts.hist_list(uid)
        self.assertEqual(len(h), 1); self.assertEqual(h[0]["p"], [40, 30, 30])


class DispatchTests(unittest.TestCase):
    def setUp(self):
        fresh_db()
        os.environ.pop("ADMIN_TOKEN", None)

    def call(self, m, p, q=None, h=None, b=None):
        return api.dispatch(m, p, q, h, b)

    def test_public_endpoints(self):
        self.assertEqual(self.call("GET", "/api/health")[0], 200)
        self.assertEqual(self.call("GET", "/api/meta")[1]["kind"], "demo")
        self.assertEqual(len(self.call("GET", "/api/teams")[1]), 16)
        self.assertEqual(len(self.call("GET", "/api/matches", {"kind": "today"})[1]), 8)
        s, r = self.call("GET", "/api/analyze", {"home": "t01", "away": "t02"})
        self.assertEqual(s, 200)
        p = r["prediction"]["percent"]; self.assertEqual(p["home"] + p["draw"] + p["away"], 100)
        self.assertEqual(self.call("GET", "/api/teams/t03")[0], 200)
        self.assertTrue(self.call("GET", "/api/quality")[1]["available"])

    def test_validation_errors(self):
        cases = [
            (("GET", "/api/analyze", {"home": "t01", "away": "t01"}), 400, "same_team"),
            (("GET", "/api/analyze", {"home": "t01", "away": "zzz"}), 404, "unknown_team"),
            (("GET", "/api/analyze", {"home": "t01"}), 422, "invalid_param"),
            (("GET", "/api/analyze", {"home": "t01", "away": "t02", "n": "99"}), 422, "invalid_param"),
            (("GET", "/api/analyze", {"home": "t01", "away": "t02", "n": "x"}), 422, "invalid_param"),
            (("GET", "/api/analyze", {"home": "../etc", "away": "t02"}), 422, "invalid_param"),
            (("GET", "/api/matches", {"kind": "bad"}), 422, "invalid_param"),
            (("GET", "/api/teams/nope"), 404, "not_found"),
            (("GET", "/api/nothing"), 404, "not_found"),
            (("GET", "/api/favorites"), 401, "auth_required"),
            (("POST", "/api/auth/login", None, None, "not-a-dict"), 400, "invalid_body"),
        ]
        for args, status, code in cases:
            s, r = self.call(*args)
            self.assertEqual((s, r["error"]["code"]), (status, code), args)

    def test_auth_flow_and_favorites(self):
        s, r = self.call("POST", "/api/auth/register", b={"email": "u@example.com", "password": "password123"})
        self.assertEqual(s, 200)
        h = {"Authorization": "Bearer " + r["token"]}
        self.assertEqual(self.call("GET", "/api/me", h=h)[1]["user"]["email"], "u@example.com")
        s, favs = self.call("POST", "/api/favorites", h=h, b={"home": "t01", "away": "t02"})
        self.assertEqual(favs, [{"home": "t01", "away": "t02"}])
        self.assertEqual(self.call("POST", "/api/favorites", h=h, b={"home": "t01", "away": "t01"})[1]["error"]["code"], "same_team")
        self.call("GET", "/api/analyze", {"home": "t03", "away": "t04"}, h)       # يسجَّل في السجل لأن المستخدم مسجَّل
        hist = self.call("GET", "/api/history", h=h)[1]
        self.assertEqual((hist[0]["home"], hist[0]["away"]), ("t03", "t04"))
        s, sync = self.call("POST", "/api/sync", h=h, b={"favorites": [{"home": "t05", "away": "t06"}, {"home": "bad", "away": "t06"}],
                                                       "history": [{"home": "t05", "away": "t06", "p": [1, 2, 97]}, {"home": "t05", "away": "t06", "p": ["x"]}]})
        self.assertEqual(len(sync["favorites"]), 2)       # الصالح فقط
        self.assertEqual(self.call("DELETE", "/api/favorites", {"home": "t01", "away": "t02"}, h)[1], [{"home": "t05", "away": "t06"}])
        self.call("POST", "/api/auth/logout", h=h)
        self.assertEqual(self.call("GET", "/api/me", h=h)[0], 401)

    def test_admin_protection(self):
        self.assertEqual(self.call("GET", "/api/admin/summary")[1]["error"]["code"], "admin_disabled")
        os.environ["ADMIN_TOKEN"] = "s3cret-token"
        self.assertEqual(self.call("GET", "/api/admin/summary", h={"X-Admin-Token": "wrong"})[0], 403)
        self.assertEqual(self.call("GET", "/api/admin/summary")[0], 403)
        s, r = self.call("GET", "/api/admin/summary", h={"x-admin-token": "s3cret-token"})
        self.assertEqual(s, 200)
        self.assertIn("live_quality", r); self.assertEqual(r["database"]["users"], 0)
        os.environ.pop("ADMIN_TOKEN")

    def test_prediction_logging_resolution(self):
        today_match = service.list_matches("today")[0]
        s, r = self.call("GET", "/api/analyze", {"home": today_match["home"], "away": today_match["away"], "match_id": today_match["id"]})
        self.assertEqual(s, 200)
        self.call("GET", "/api/analyze", {"home": today_match["home"], "away": today_match["away"], "match_id": today_match["id"]})  # لا تكرار في نفس اليوم
        ev = monitor.evaluate()
        self.assertEqual((ev["logged"], ev["resolved"], ev["pending"]), (1, 0, 1))
        # محاكاة انتهاء المباراة وتحديث نتيجتها في قاعدة البيانات
        with db.connect() as con:
            con.execute("INSERT INTO matches(id,date,home,away,hg,ag,status,source) VALUES(?,?,?,?,?,?,?,?)",
                        (today_match["id"], today_match["date"], today_match["home"], today_match["away"], 2, 0, "played", "test"))
        ev = monitor.evaluate()
        self.assertEqual(ev["resolved"], 1); self.assertTrue(0 <= ev["brier"] <= 2)
        # مباراة منتهية أصلًا لا تُسجَّل كتوقع
        played = service.list_matches("results")[0]
        self.call("GET", "/api/analyze", {"home": played["home"], "away": played["away"], "match_id": played["id"]})
        self.assertEqual(monitor.evaluate()["logged"], 1)


class ImporterTests(unittest.TestCase):
    def setUp(self):
        fresh_db()
        # بيانات المحاكاة: نفس المباريات التجريبية بمعرّفات رقمية، وبعض المباريات القادمة قريبة من اليوم
        self.ds = build_dataset()
        self.fake = FakeFootballApi(self.ds)

    def tearDown(self):
        self.fake.close()

    def client(self, **kw):
        return provider.Client(key="test-key", base=self.fake.url, min_interval=0, **kw)

    def test_import_replaces_demo_and_serves_real_path(self):
        c = self.client()
        s = importer.run(c, 39, 2026, stats_last=3, availability=1, log=lambda *_: None)
        self.assertEqual(s["teams"], 16); self.assertEqual(s["stats"], 3); self.assertEqual(s["availability"], 1)
        self.assertEqual(set(self.fake.keys), {"test-key"})
        self.assertNotIn("999999", json.dumps(self.fake.calls))          # المؤجلة ليست في الاستيراد (لا تُخزَّن)
        with db.connect() as con:
            self.assertEqual(con.execute("SELECT COUNT(*) c FROM matches").fetchone()["c"], 480)
            self.assertEqual(db.kv_get(con, "requests_remaining"), str(c.remaining))
        self.assertEqual(service.meta()["kind"], "api-football")
        with db.connect() as con:      # أول فريقين لهما إحصائيات مستوردة
            row = con.execute("SELECT m.home, m.away FROM match_stats s JOIN matches m ON m.id=s.match_id LIMIT 1").fetchone()
        r = api.dispatch("GET", "/api/analyze", {"home": row["home"], "away": row["away"]})[1]
        self.assertEqual(r["data_kind"], "api-football")
        self.assertIsNotNone(r["stats"])                                 # الإحصائيات ظهرت بعد الاستيراد
        self.assertEqual(r["stats"]["home"]["matches"], 1)
        t = api.dispatch("GET", "/api/teams/" + row["home"])[1]
        self.assertIsNotNone(t["stats"])
        self.assertEqual(api.dispatch("GET", "/api/analyze", {"home": "a1", "away": "a2"})[1]["data_kind"], "api-football")
        self.assertEqual(api.dispatch("GET", "/api/matches", {"kind": "today"})[0], 200)

    def test_availability_in_context(self):
        importer.run(self.client(), 39, 2026, availability=100, log=lambda *_: None)
        up = service.list_matches("upcoming")[0]
        r = api.dispatch("GET", "/api/analyze", {"home": up["home"], "away": up["away"], "match_id": up["id"]})[1]
        self.assertIsNotNone(r["context"])
        self.assertEqual(list(r["context"]["lineups"].values())[0]["formation"], "4-3-3")
        self.assertEqual(r["context"]["injuries"][0]["reason"], "Knee Injury")
        self.assertNotIn({"k": "no_availability"}, r["missing_data"])

    def test_budget_reserve_stops_import(self):
        self.fake.remaining = 14      # بعد طلب المباريات يصبح 13؛ الاحتياطي 12 => طلبان فقط
        c = self.client(reserve=12)
        s = importer.run(c, 39, 2026, stats_last=50, log=lambda *_: None)
        self.assertIsNotNone(s["stopped"])
        self.assertLessEqual(s["stats"], 2)
        self.assertGreaterEqual(c.remaining, 11)

    def test_provider_errors_are_clear(self):
        self.fake.mode = "errors"
        with self.assertRaises(provider.ProviderError) as e:
            importer.run(self.client(), 39, 2019, log=lambda *_: None)
        self.assertIn("plan", str(e.exception))
        with self.assertRaises(provider.ProviderError):
            provider.Client(key="", base=self.fake.url) if not os.environ.get("API_FOOTBALL_KEY") else (_ for _ in ()).throw(provider.ProviderError())

    def test_mapping_functions(self):
        self.assertEqual(provider.map_statistics([{"team": {"id": 7}, "statistics": [{"type": "Ball Possession", "value": "61%"}]}]),
                         {"a7": {"possession": 61.0, "shots": None, "shots_on": None, "corners": None}})
        fx = {"fixture": {"id": 5, "date": "2026-10-12T19:00:00+00:00", "status": {"short": "1H"}}, "teams": {"home": {"id": 1, "name": "a"}, "away": {"id": 2, "name": "b"}}, "goals": {}}
        self.assertIsNone(provider.map_fixture(fx))                      # مباراة جارية تُتجاهل


class FootballDataTests(unittest.TestCase):
    def setUp(self):
        fresh_db()
        self.ds = build_dataset()
        self.fake = FakeFootballData(self.ds)

    def tearDown(self):
        self.fake.close()

    def client(self, key="fd-key"):
        return provider.FootballDataClient(key=key, base=self.fake.url, min_interval=0)

    def test_import_and_serve(self):
        s = importer.run_fd(self.client(), "PL", log=lambda *_: None)
        self.assertEqual((s["matches"], s["teams"], s["requests"]), (480, 16, 1))      # 3 مباريات غير صالحة تُتجاهل
        self.assertEqual(self.fake.calls[0][0], "/competitions/PL/matches")
        self.assertNotIn("season", self.fake.calls[0][1])                              # الافتراضي: الموسم الحالي
        m = service.meta()
        self.assertEqual((m["kind"], m["league"]), ("football-data", "Premier League"))
        self.assertTrue(service.list_teams()[0]["id"].startswith("f"))
        today = service.list_matches("today")
        self.assertEqual(len(today), 8)                                                # مباريات تاريخ اليوم تظهر كـ«اليوم»
        a = api.dispatch("GET", "/api/analyze", {"home": today[0]["home"], "away": today[0]["away"], "match_id": today[0]["id"]})[1]
        self.assertEqual(a["data_kind"], "football-data")
        self.assertIsNone(a["stats"])
        self.assertEqual(monitor.evaluate()["logged"], 1)                              # التوقع سُجّل للمراقبة
        self.assertGreater(len(service.list_matches("results")), 0)

    def test_two_sources_coexist_per_league(self):
        importer.run_fd(self.client(), "PL", log=lambda *_: None)
        accounts_mod.register("keep@example.com", "password123")
        fb = FakeFootballApi(self.ds)
        try:
            importer.run(provider.Client(key="k", base=fb.url, min_interval=0), 233, 2024, log=lambda *_: None)   # مصدر آخر في نفس القاعدة
        finally:
            fb.close()
        ls = {l["code"]: l for l in service.leagues()}
        self.assertEqual(set(ls), {"PL", "233"})
        self.assertEqual((ls["PL"]["source"], ls["233"]["source"]), ("football-data", "api-football"))
        self.assertEqual(ls["233"]["name"], "Test League (Egypt)")                      # الاسم مع الدولة
        self.assertTrue(ls["PL"]["current"])                                           # فيها مباريات اليوم/القادمة
        pl_team = service.list_teams(league="PL")[0]["id"]; eg_team = service.list_teams(league="233")[0]["id"]
        self.assertTrue(pl_team.startswith("f") and eg_team.startswith("a"))
        r = api.dispatch("GET", "/api/analyze", {"home": eg_team, "away": service.list_teams(league="233")[1]["id"]})[1]
        self.assertEqual(r["data_kind"], "api-football")
        self.assertEqual(api.dispatch("GET", "/api/teams/" + pl_team)[1]["data_kind"], "football-data")
        self.assertIsNotNone(accounts_mod.login("keep@example.com", "password123"))     # الحسابات سليمة
        importer.run_fd(self.client(), "PL", replace=True, log=lambda *_: None)          # --replace يمسح كل شيء صراحةً
        self.assertEqual([l["code"] for l in service.leagues()], ["PL"])

    def test_find_league_ids(self):
        fb = FakeFootballApi(self.ds)
        try:
            out = importer.find_leagues(provider.Client(key="k", base=fb.url, min_interval=0), "egypt", log=lambda *_: None)
        finally:
            fb.close()
        self.assertEqual(out, [{"id": 233, "name": "Premier League", "country": "Egypt", "seasons": "2010–2024"}])

    def test_errors_are_clear(self):
        with self.assertRaises(provider.ProviderError) as e:
            importer.run_fd(self.client(key="wrong"), "PL", log=lambda *_: None)
        self.assertIn("403", str(e.exception))
        self.fake.fail = (429, "You reached your request limit.")
        with self.assertRaises(provider.ProviderError) as e:
            importer.run_fd(self.client(), "PL", log=lambda *_: None)
        self.assertIn("429", str(e.exception)); self.assertIn("request limit", str(e.exception))
        if not os.environ.get("FOOTBALL_DATA_KEY"):
            with self.assertRaises(provider.ProviderError):
                provider.FootballDataClient(key="")


class RefreshAndBackupTests(unittest.TestCase):
    def setUp(self):
        fresh_db()
        self.ds = build_dataset()
        self.fake = FakeFootballData(self.ds)

    def tearDown(self):
        self.fake.close()

    def client(self):
        return provider.FootballDataClient(key="fd-key", base=self.fake.url, min_interval=0)

    def test_refresh_updates_results_and_records_state(self):
        self.assertFalse(autorefresh.refresh_once(self.client()))                  # لا مصدر حقيقي بعد: لا شيء يحدث
        importer.run_fd(self.client(), "PL", log=lambda *_: None)
        before = len(service.list_matches("results"))
        # في الخادم المحاكي: مباراة اليوم الأولى تنتهي بنتيجة 3-1
        m = next(x for x in self.ds["matches"] if x["status"] == "today")
        m["status"], m["hg"], m["ag"] = "played", 3, 1
        self.assertTrue(autorefresh.refresh_once(self.client()))
        self.assertEqual(len([x for x in service.list_matches("today")]), 7)
        with db.connect() as con:
            self.assertTrue(db.kv_get(con, "last_refresh")); self.assertEqual(db.kv_get(con, "refresh_error"), "")
            self.assertEqual(con.execute("SELECT hg, ag FROM matches WHERE id=?", ("fm" + str(5000 + self.ds["matches"].index(m)),)).fetchone()[:], (3, 1))
        self.assertGreaterEqual(len(service.list_matches("results")), min(before, 16))

    def test_refresh_errors_are_recorded_not_raised(self):
        importer.run_fd(self.client(), "PL", log=lambda *_: None)
        self.fake.fail = (429, "limit")
        self.assertFalse(autorefresh.refresh_once(self.client()))                  # لا يرفع استثناءً
        s, r = api.dispatch("GET", "/api/admin/summary", headers={"X-Admin-Token": "t"})
        os.environ["ADMIN_TOKEN"] = "t"
        s, r = api.dispatch("GET", "/api/admin/summary", headers={"X-Admin-Token": "t"})
        os.environ.pop("ADMIN_TOKEN")
        self.assertIn("429", r["database"]["refresh_error"])
        self.assertEqual(service.meta()["kind"], "football-data")                  # البيانات القديمة سليمة

    def test_placeholder_key_is_rejected_clearly(self):
        for bad in ("مفتاحك", "abc def"):
            with self.assertRaises(provider.ProviderError) as e:
                provider.FootballDataClient(key=bad)
            self.assertIn("FOOTBALL_DATA_KEY", str(e.exception))
        with self.assertRaises(provider.ProviderError):
            provider.Client(key="مفتاحك")
        importer.run_fd(self.client(), "PL", log=lambda *_: None)
        os.environ["FOOTBALL_DATA_KEY"] = "مفتاحك"
        try:
            self.assertFalse(autorefresh.refresh_once())                      # لا ينهار؛ يسجّل الخطأ
        finally:
            os.environ.pop("FOOTBALL_DATA_KEY")
        with db.connect() as con:
            self.assertIn("FOOTBALL_DATA_KEY", db.kv_get(con, "refresh_error"))

    def test_refresh_ignores_other_sources(self):
        fb = FakeFootballApi(self.ds)
        try:
            importer.run(provider.Client(key="k", base=fb.url, min_interval=0), 39, 2026, log=lambda *_: None)
        finally:
            fb.close()
        self.assertFalse(autorefresh.refresh_once(self.client()))                  # API-Football لا يُحدَّث تلقائيًا
        self.assertEqual(self.fake.calls, [])

    def test_backup_is_consistent_and_rotates(self):
        uid = accounts_mod.register("bk@example.com", "password123")["user"]["id"]
        for _ in range(9):
            out = backup.run()
        files = sorted(out.parent.glob("smm-*.db"))
        self.assertLessEqual(len(files), backup.KEEP)
        import sqlite3
        c = sqlite3.connect(out)
        self.assertEqual(c.execute("SELECT email FROM users").fetchone()[0], "bk@example.com")
        c.close()


def _second_league(ds):
    """بطولة ثانية بفرق مختلفة (t101..t116) ونتائج مستقلة قليلًا عن الأولى."""
    ren = {t["id"]: "t1" + t["id"][1:] for t in ds["teams"]}
    return {"meta": ds["meta"], "teams": [{**t, "id": ren[t["id"]], "name": t["name"] + " B"} for t in ds["teams"]],
            "matches": [{**m, "home": ren[m["home"]], "away": ren[m["away"]], "id": m["id"] + "b"} for m in ds["matches"]]}


class MultiLeagueTests(unittest.TestCase):
    def setUp(self):
        fresh_db()
        self.a = build_dataset()
        self.b = _second_league(self.a)
        self.fake = FakeFootballData(self.a, datasets={"PL": self.a, "PD": self.b})

    def tearDown(self):
        self.fake.close()

    def client(self):
        return provider.FootballDataClient(key="fd-key", base=self.fake.url, min_interval=0)

    def load(self):
        c = self.client()
        importer.run_fd(c, "PL", replace=True, log=lambda *_: None)
        importer.run_fd(c, "PD", log=lambda *_: None)                    # البطولة الثانية تُضاف ولا تستبدل الأولى

    def test_two_leagues_are_kept_separate(self):
        self.load()
        ls = api.dispatch("GET", "/api/leagues")[1]
        self.assertEqual([(l["code"], l["name"], l["teams"]) for l in ls], [("PL", "Premier League", 16), ("PD", "Primera Division", 16)])
        self.assertEqual(len(api.dispatch("GET", "/api/teams")[1]), 32)
        pd = api.dispatch("GET", "/api/teams", {"league": "PD"})[1]
        self.assertEqual(len(pd), 16); self.assertTrue(all(t["league"] == "PD" for t in pd))
        today_pl = api.dispatch("GET", "/api/matches", {"kind": "today", "league": "PL"})[1]
        today_pd = api.dispatch("GET", "/api/matches", {"kind": "today", "league": "PD"})[1]
        self.assertEqual((len(today_pl), len(today_pd)), (8, 8))
        self.assertTrue(set(m["home"] for m in today_pl).isdisjoint(m["home"] for m in today_pd))

    def test_analysis_within_league_and_cross_league_rejected(self):
        self.load()
        pl, pd = api.dispatch("GET", "/api/teams", {"league": "PL"})[1], api.dispatch("GET", "/api/teams", {"league": "PD"})[1]
        s, r = api.dispatch("GET", "/api/analyze", {"home": pd[0]["id"], "away": pd[1]["id"]})
        self.assertEqual(s, 200); self.assertEqual(r["league"]["code"], "PD")
        s, r = api.dispatch("GET", "/api/analyze", {"home": pl[0]["id"], "away": pd[0]["id"]})
        self.assertEqual((s, r["error"]["code"]), (400, "different_leagues"))
        self.assertEqual(api.dispatch("GET", "/api/teams/" + pd[0]["id"])[1]["team"]["league"], "PD")

    def test_quality_per_league_and_unknown_league(self):
        self.load()
        for code in ("PL", "PD"):
            q = api.dispatch("GET", "/api/quality", {"league": code})[1]
            self.assertTrue(q["available"]); self.assertEqual(q["league"], code)
        self.assertEqual(api.dispatch("GET", "/api/quality")[1]["league"], "PL")             # الافتراضي: أول بطولة
        s, r = api.dispatch("GET", "/api/quality", {"league": "XX"})
        self.assertEqual((s, r["error"]["code"]), (404, "unknown_league"))
        self.assertEqual(api.dispatch("GET", "/api/matches", {"kind": "today", "league": "../x"})[0], 422)

    def test_refresh_updates_all_leagues(self):
        self.load()
        self.fake.calls.clear()
        self.assertTrue(autorefresh.refresh_once(self.client()))
        self.assertEqual(sorted(c[0] for c in self.fake.calls), ["/competitions/PD/matches", "/competitions/PL/matches"])
        self.fake.fail = (429, "limit")
        self.assertFalse(autorefresh.refresh_once(self.client()))

    def test_legacy_database_without_leagues_table_rows(self):
        importer.run_fd(self.client(), "PL", replace=True, log=lambda *_: None)
        with db.connect() as con:                                        # محاكاة قاعدة قديمة: league=اسم البطولة، لا صفوف في leagues
            con.execute("DELETE FROM leagues"); con.execute("UPDATE matches SET league='Premier League'")
            db.kv_set(con, "version", "legacy")
        ls = api.dispatch("GET", "/api/leagues")[1]
        self.assertEqual([(l["code"], l["name"]) for l in ls], [("Premier League", "Premier League")])
        self.assertEqual(api.dispatch("GET", "/api/quality", {"league": "Premier League"})[0], 422)  # المسافة غير مسموحة في المعرّف؛ تُصلَح بإعادة الاستيراد


class HighlightlyTests(unittest.TestCase):
    def setUp(self):
        fresh_db()
        self.ds = build_dataset()
        self.fake = FakeHighlightly(self.ds)

    def tearDown(self):
        self.fake.close()

    def client(self, **kw):
        return provider.HighlightlyClient(key="hl-key", base=self.fake.url, min_interval=0, **kw)

    def test_import_paginates_and_filters_states(self):
        c = self.client()
        r = importer.run_hl(c, 199067, 2026, log=lambda *_: None)
        self.assertEqual((r["matches"], r["teams"], r["reported_total"], r["requests"]), (480, 16, 484, 5))   # 484 مباراة بينها 4 غير صالحة، في 5 صفحات
        self.assertEqual([c_[1]["offset"] for c_ in self.fake.calls], ["0", "100", "200", "300", "400"])
        self.assertEqual(c.plan["tier"], "BASIC"); self.assertEqual(c.remaining, 95)
        ls = {l["code"]: l for l in service.leagues()}
        self.assertEqual(ls["hl199067"]["name"], "Premier League (Egypt)")
        self.assertEqual((ls["hl199067"]["source"], ls["hl199067"]["season"], ls["hl199067"]["current"]), ("highlightly", "2026", True))
        self.assertTrue(service.list_teams(league="hl199067")[0]["id"].startswith("h"))
        self.assertEqual(len(service.list_matches("today", "hl199067")), 8)
        t = service.list_teams(league="hl199067")
        r = api.dispatch("GET", "/api/analyze", {"home": t[0]["id"], "away": t[1]["id"]})[1]
        self.assertEqual(r["data_kind"], "highlightly")
        self.assertTrue(api.dispatch("GET", "/api/quality", {"league": "hl199067"})[1]["available"])
        with db.connect() as con:
            self.assertEqual(db.kv_get(con, "hl_leagues"), "199067:2026")

    def test_three_sources_coexist(self):
        importer.run_hl(self.client(), 199067, 2026, log=lambda *_: None)
        fd = FakeFootballData(self.ds)
        try:
            importer.run_fd(provider.FootballDataClient(key="fd-key", base=fd.url, min_interval=0), "PL", log=lambda *_: None)
        finally:
            fd.close()
        self.assertEqual({l["code"]: l["source"] for l in service.leagues()}, {"hl199067": "highlightly", "PL": "football-data"})

    def test_errors_and_budget(self):
        with self.assertRaises(provider.ProviderError) as e:
            importer.run_hl(provider.HighlightlyClient(key="wrong", base=self.fake.url, min_interval=0), 199067, 2026, log=lambda *_: None)
        self.assertIn("401", str(e.exception))
        with self.assertRaises(provider.ProviderError):
            provider.HighlightlyClient(key="مفتاحك")
        self.fake.remaining = 17                                              # الاحتياطي 15: يتوقف بعد طلبين
        with self.assertRaises(provider.BudgetExhausted):
            importer.run_hl(self.client(), 199067, 2026, log=lambda *_: None)
        self.fake.remaining = 100
        with self.assertRaises(provider.ProviderError) as e:
            importer.run_hl(self.client(), 12345, 2026, log=lambda *_: None)      # دوري غير موجود: لا مباريات
        self.assertIn("مباريات صالحة", str(e.exception))

    def test_find_leagues(self):
        out = importer.find_hl_leagues(self.client(), "Egypt", log=lambda *_: None)
        self.assertEqual(out[0], {"id": 199067, "name": "Premier League", "last_season": 2026})

    def test_refresh_updates_and_records_errors(self):
        importer.run_hl(self.client(), 199067, 2026, log=lambda *_: None)
        m = next(x for x in self.ds["matches"] if x["status"] == "today")
        m["status"], m["hg"], m["ag"] = "played", 2, 2
        self.assertTrue(autorefresh.refresh_hl_once(self.client()))
        self.assertEqual(len(service.list_matches("today", "hl199067")), 7)
        self.fake.fail = (429, "limit")
        self.assertFalse(autorefresh.refresh_hl_once(self.client()))
        with db.connect() as con:
            self.assertIn("429", db.kv_get(con, "refresh_error_hl"))
        self.assertEqual(len(service.list_matches("today", "hl199067")), 7)             # البيانات القديمة سليمة

    def test_state_mapping(self):
        mk = lambda st, sc=None: {"id": 1, "round": "Quarter-finals", "date": "2026-10-20T18:30:00.000Z", "homeTeam": {"id": 1, "name": "A"},
                                  "awayTeam": {"id": 2, "name": "B"}, "league": {"id": 5, "season": 2026, "name": "L"}, "state": {"description": st, "score": {"current": sc}}}
        r = provider.map_hl_match(mk("Finished after penalties", "1 - 1"), "hl5")
        self.assertEqual((r["status"], r["hg"], r["ag"], r["round"], r["time"]), ("played", 1, 1, None, "18:30"))
        self.assertEqual(provider.map_hl_match(mk("Not started"), "hl5")["status"], "scheduled")
        for st in ("Postponed", "To be announced", "Second half", "Awarded", "Cancelled"):
            self.assertIsNone(provider.map_hl_match(mk(st, "1 - 0"), "hl5"))
        self.assertIsNone(provider.map_hl_match(mk("Finished", "bad"), "hl5"))


class HighlightlyTests(unittest.TestCase):
    def setUp(self):
        fresh_db()
        self.ds = build_dataset()
        self.fake = FakeHighlightly(self.ds)

    def tearDown(self):
        self.fake.close()

    def client(self, key="hl-key", **kw):
        return provider.HighlightlyClient(key=key, base=self.fake.url, min_interval=0, **kw)

    def test_import_paginates_and_filters_states(self):
        r = importer.run_hl(self.client(), 199067, 2026, log=lambda *_: None)
        self.assertEqual((r["matches"], r["teams"], r["reported_total"]), (480, 16, 484))      # 4 حالات غير صالحة تُتجاهل
        self.assertEqual(r["requests"], 5)                                                     # 484 مباراة = 5 صفحات
        self.assertTrue(all(c[1]["leagueId"] == "199067" and c[1]["season"] == "2026" for c in self.fake.calls))
        ls = {l["code"]: l for l in service.leagues()}
        self.assertEqual(ls["hl199067"]["name"], "Premier League (Egypt)")
        self.assertEqual((ls["hl199067"]["source"], ls["hl199067"]["season"]), ("highlightly", "2026"))
        self.assertTrue(ls["hl199067"]["current"])                                             # فيها مباريات اليوم/القادمة
        teams = service.list_teams(league="hl199067")
        self.assertTrue(all(t["id"].startswith("h") for t in teams))
        res = api.dispatch("GET", "/api/analyze", {"home": teams[0]["id"], "away": teams[1]["id"]})[1]
        self.assertEqual(res["data_kind"], "highlightly")
        self.assertTrue(api.dispatch("GET", "/api/quality", {"league": "hl199067"})[1]["available"])
        self.assertEqual(len(service.list_matches("today", "hl199067")), 8)

    def test_coexists_with_other_sources(self):
        fd = FakeFootballData(self.ds)
        try:
            importer.run_fd(provider.FootballDataClient(key="fd-key", base=fd.url, min_interval=0), "PL", log=lambda *_: None)
        finally:
            fd.close()
        importer.run_hl(self.client(), 199067, 2026, log=lambda *_: None)
        self.assertEqual({l["code"]: l["source"] for l in service.leagues()}, {"PL": "football-data", "hl199067": "highlightly"})

    def test_budget_reserve_and_errors(self):
        self.fake.remaining = 17                       # بعد طلبين يصل إلى 15 = الاحتياطي
        with self.assertRaises(provider.BudgetExhausted):
            importer.run_hl(self.client(reserve=15), 199067, 2026, log=lambda *_: None)
        self.fake.remaining = 100
        with self.assertRaises(provider.ProviderError) as e:
            importer.run_hl(self.client(key="wrong"), 199067, 2026, log=lambda *_: None)
        self.assertIn("401", str(e.exception))
        with self.assertRaises(provider.ProviderError):
            importer.run_hl(self.client(), 111, 2026, log=lambda *_: None)                   # دوري لا مباريات فيه
        for bad in ("مفتاحك", "a b"):
            with self.assertRaises(provider.ProviderError):
                provider.HighlightlyClient(key=bad)

    def test_find_leagues(self):
        out = importer.find_hl_leagues(self.client(), "Egypt", log=lambda *_: None)
        self.assertEqual([(l["id"], l["name"], l["last_season"]) for l in out], [(199067, "Premier League", 2026), (459473, "Super Cup", 2025)])

    def test_refresh_updates_and_records_errors(self):
        importer.run_hl(self.client(), 199067, 2026, log=lambda *_: None)
        m = next(x for x in self.ds["matches"] if x["status"] == "today")
        m["status"], m["hg"], m["ag"] = "played", 2, 2
        self.assertTrue(autorefresh.refresh_hl_once(self.client()))
        self.assertEqual(len(service.list_matches("today", "hl199067")), 7)
        self.fake.fail = (429, "limit")
        self.assertFalse(autorefresh.refresh_hl_once(self.client()))
        os.environ["ADMIN_TOKEN"] = "t"
        r = api.dispatch("GET", "/api/admin/summary", headers={"X-Admin-Token": "t"})[1]
        os.environ.pop("ADMIN_TOKEN")
        self.assertIn("429", r["database"]["refresh_error_hl"])
        self.assertEqual(len(service.list_matches("today", "hl199067")), 7)                  # البيانات السابقة سليمة


class PublishReadinessTests(unittest.TestCase):
    def setUp(self):
        fresh_db()
        os.environ.pop("ADMIN_TOKEN", None)

    def register(self, email="del@example.com"):
        r = api.dispatch("POST", "/api/auth/register", body={"email": email, "password": "password123"})[1]
        return {"Authorization": "Bearer " + r["token"]}, r["user"]["id"]

    def test_delete_account_removes_everything(self):
        h, uid = self.register()
        s, favs = api.dispatch("POST", "/api/favorites", headers=h, body={"home": "t01", "away": "t02"})
        self.assertEqual(s, 200)
        api.dispatch("GET", "/api/analyze", {"home": "t03", "away": "t04"}, h)
        self.assertEqual(api.dispatch("POST", "/api/auth/delete", headers=h, body={"password": "wrong-pass"})[0], 401)   # كلمة مرور خاطئة
        self.assertEqual(api.dispatch("GET", "/api/me", headers=h)[0], 200)                                             # الحساب ما زال موجودًا
        self.assertEqual(api.dispatch("POST", "/api/auth/delete", body={"password": "password123"})[0], 401)           # بدون تسجيل دخول
        self.assertEqual(api.dispatch("POST", "/api/auth/delete", headers=h, body={"password": "password123"})[0], 200)
        self.assertEqual(api.dispatch("GET", "/api/me", headers=h)[0], 401)                                             # الجلسة انتهت
        with db.connect() as con:
            for t in ("users", "favorites", "history", "sessions"):
                self.assertEqual(con.execute(f"SELECT COUNT(*) c FROM {t}").fetchone()["c"], 0, t)
        self.assertEqual(api.dispatch("POST", "/api/auth/login", body={"email": "del@example.com", "password": "password123"})[0], 401)

    def test_rate_limit_auth_and_general(self):
        for i in range(10):                                           # بريد مختلف كل مرة كي لا يتدخل قفل الحساب
            self.assertEqual(api.dispatch("POST", "/api/auth/login", body={"email": f"x{i}@example.com", "password": "password123"})[0], 401)
        s, r = api.dispatch("POST", "/api/auth/login", body={"email": "x99@example.com", "password": "password123"})
        self.assertEqual((s, r["error"]["code"]), (429, "rate_limited"))
        api._reset_limits()
        self.assertEqual(api.dispatch("POST", "/api/auth/login", body={"email": "x100@example.com", "password": "password123"})[0], 401)
        api._reset_limits()
        old = api.LIMIT_GENERAL
        api.LIMIT_GENERAL = (5, 60)
        try:
            codes = [api.dispatch("GET", "/api/health")[0] for _ in range(7)]
        finally:
            api.LIMIT_GENERAL = old
        self.assertEqual(codes, [200] * 5 + [429] * 2)

    def test_limit_is_per_client_and_proxy_header_only_trusted_from_loopback(self):
        old = api.LIMIT_GENERAL
        api.LIMIT_GENERAL = (2, 60)
        try:
            a = {"x-smm-peer": "127.0.0.1", "cf-connecting-ip": "1.1.1.1"}
            b = {"x-smm-peer": "127.0.0.1", "cf-connecting-ip": "2.2.2.2"}
            self.assertEqual([api.dispatch("GET", "/api/health", headers=a)[0] for _ in range(3)], [200, 200, 429])
            self.assertEqual(api.dispatch("GET", "/api/health", headers=b)[0], 200)                  # عميل آخر لا يتأثر
            spoof = {"x-smm-peer": "9.9.9.9", "cf-connecting-ip": "3.3.3.3"}                          # ترويسة مزوّرة من عنوان خارجي
            self.assertEqual([api.dispatch("GET", "/api/health", headers=spoof)[0] for _ in range(3)], [200, 200, 429])
            self.assertEqual(api.dispatch("GET", "/api/health", headers={"x-smm-peer": "9.9.9.9", "cf-connecting-ip": "4.4.4.4"})[0], 429)
        finally:
            api.LIMIT_GENERAL = old

    def test_legal_pages_manifest_and_headers_over_http(self):
        import server_lite
        srv = server_lite.ThreadingHTTPServer(("127.0.0.1", 0), server_lite.Handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        try:
            for page in ("/privacy.html", "/terms.html"):
                with urllib.request.urlopen(base + page) as r:
                    body = r.read().decode("utf-8")
                    self.assertEqual(r.status, 200)
                    self.assertIn("CONTACT_EMAIL", body)                                              # يذكّر بوضع بريدك الحقيقي
                    self.assertEqual(r.headers["X-Frame-Options"], "DENY")
                    self.assertEqual(r.headers["Referrer-Policy"], "no-referrer")
            os.environ["SMM_CONTACT_EMAIL"] = "owner@example.org"
            with urllib.request.urlopen(base + "/privacy.html") as r:
                body = r.read().decode("utf-8")
            os.environ.pop("SMM_CONTACT_EMAIL")
            self.assertIn("owner@example.org", body); self.assertNotIn("CONTACT_EMAIL", body)       # يُستبدل من متغير البيئة
            with urllib.request.urlopen(base + "/manifest.webmanifest") as r:
                mf = json.loads(r.read())
            self.assertIn("maskable", [i["purpose"] for i in mf["icons"]])
            self.assertEqual((mf["display"], mf["id"]), ("standalone", "/"))
            with urllib.request.urlopen(base + "/icons/icon-512-maskable.png") as r:
                self.assertEqual(r.status, 200)
        finally:
            srv.shutdown(); srv.server_close()


class HighlightlyExtrasTests(unittest.TestCase):
    def setUp(self):
        fresh_db()
        self.ds = build_dataset()
        self.fake = FakeHighlightly(self.ds)
        self.c = provider.HighlightlyClient(key="hl-key", base=self.fake.url, min_interval=0)
        importer.run_hl(self.c, 199067, 2026, log=lambda *_: None)
        self.fake.calls.clear()

    def tearDown(self):
        self.fake.close()

    def test_mapping(self):
        detail = {"statistics": [
            {"team": {"id": 5}, "statistics": [{"value": 0.57, "displayName": "Possession"}, {"value": 5, "displayName": "Shots on target"},
                                               {"value": 4, "displayName": "Shots off target"}, {"value": 3, "displayName": "Blocked shots"}, {"value": 7, "displayName": "Corners"}]},
            {"team": {"id": 6}, "statistics": [{"value": 43, "displayName": "Possession"}, {"value": 2, "displayName": "Shots on target"}]},
            {"team": {"id": 9}, "statistics": [{"value": 1, "displayName": "Corners"}]}]}
        r = provider.map_hl_statistics(detail, {"h5", "h6"})
        self.assertEqual(r["h5"], {"possession": 57.0, "shots": 12, "shots_on": 5, "corners": 7})
        self.assertEqual((r["h6"]["possession"], r["h6"]["shots"], r["h6"]["shots_on"]), (43.0, None, 2))   # لا نفترض إجمالي التسديدات إن نقصت أجزاؤه
        self.assertNotIn("h9", r)                                                                           # فريق ليس طرفًا في المباراة
        self.assertEqual(provider.map_hl_statistics({}, {"h5"}), {})

    def test_stats_import_flows_to_analysis_and_is_not_repeated(self):
        got = importer.run_hl_stats(self.c, 3, log=lambda *_: None)
        self.assertEqual((got, len(self.fake.calls)), (3, 3))
        with db.connect() as con:
            r = con.execute("SELECT possession, shots, shots_on, corners FROM match_stats LIMIT 1").fetchone()
            self.assertEqual(tuple(r), (57.0, 12, 5, 7)) if r["possession"] == 57.0 else None
            row = con.execute("SELECT m.home, m.away FROM match_stats s JOIN matches m ON m.id=s.match_id LIMIT 1").fetchone()
        a = api.dispatch("GET", "/api/analyze", {"home": row["home"], "away": row["away"]})[1]
        self.assertIsNotNone(a["stats"]); self.assertNotIn({"k": "no_stats"}, a["missing_data"])
        self.fake.calls.clear()
        importer.run_hl_stats(self.c, 3, log=lambda *_: None)
        self.assertEqual(len(self.fake.calls), 3)                                   # الدفعة التالية لا تكرّر السابقة
        with db.connect() as con:
            self.assertEqual(con.execute("SELECT COUNT(DISTINCT match_id) c FROM match_stats").fetchone()["c"], 6)

    def test_empty_stats_marked_and_not_retried(self):
        with db.connect() as con:
            newest = con.execute("SELECT id FROM matches WHERE status='played' ORDER BY date DESC, id DESC LIMIT 1").fetchone()["id"]
        self.fake.no_stats_ids = (int(newest[2:]),)
        importer.run_hl_stats(self.c, 1, log=lambda *_: None)
        with db.connect() as con:
            self.assertEqual(con.execute("SELECT COUNT(*) c FROM stats_tried").fetchone()["c"], 1)
        self.fake.calls.clear()
        importer.run_hl_stats(self.c, 1, log=lambda *_: None)
        self.assertNotIn("/matches/" + newest[2:], [c[0] for c in self.fake.calls])

    def test_lineups_only_when_confirmed_and_shown_in_context(self):
        got = importer.run_hl_lineups(self.c, 1, log=lambda *_: None)
        self.assertGreater(got, 0); self.assertLess(got, 8)                         # بعضها لم يُؤكَّد فتُجوهِل
        today = service.list_matches("today", "hl199067")
        with_l = next(m for m in today if api.dispatch("GET", "/api/analyze", {"home": m["home"], "away": m["away"], "match_id": m["id"]})[1]["context"])
        ctx = api.dispatch("GET", "/api/analyze", {"home": with_l["home"], "away": with_l["away"], "match_id": with_l["id"]})[1]["context"]
        self.assertEqual(ctx["lineups"][with_l["home"]]["formation"], "4-3-3")
        self.assertTrue(ctx["lineups"][with_l["home"]]["start"][0].startswith("GK"))

    def test_budget_and_rate_limit_stop_extras(self):
        self.fake.remaining = 17                      # الخادم يعيد الرصيد في ترويسة كل رد: 16 ثم 15 = الاحتياطي
        with self.assertRaises(provider.BudgetExhausted):
            importer.run_hl_stats(self.c, 8, log=lambda *_: None)
        self.fake.fail = (429, "slow down")
        c2 = provider.HighlightlyClient(key="hl-key", base=self.fake.url, min_interval=0)
        with self.assertRaises(provider.RateLimited):
            importer.run_hl_stats(c2, 8, log=lambda *_: None)

    def test_auto_refresh_includes_extras_and_records_errors(self):
        self.assertTrue(autorefresh.refresh_hl_once(self.c))
        with db.connect() as con:
            self.assertGreater(con.execute("SELECT COUNT(DISTINCT match_id) c FROM match_stats").fetchone()["c"], 0)
        os.environ["SMM_HL_EXTRAS"] = "0"
        try:
            n = len(self.fake.calls)
            self.assertTrue(autorefresh.refresh_hl_once(self.c))
            self.assertFalse(any(c[0].startswith(("/lineups/", "/matches/70")) for c in self.fake.calls[n:]))     # بلا إضافات
        finally:
            os.environ.pop("SMM_HL_EXTRAS")


class LeagueDuplicatesTests(unittest.TestCase):
    def setUp(self):
        fresh_db()
        self.ds = build_dataset()
        self.hl, self.fb = FakeHighlightly(self.ds), FakeFootballApi(self.ds)

    def tearDown(self):
        self.hl.close(); self.fb.close()

    def load(self):
        importer.run(provider.Client(key="k", base=self.fb.url, min_interval=0), 233, 2024, log=lambda *_: None)       # أرشيف
        importer.run_hl(provider.HighlightlyClient(key="hl-key", base=self.hl.url, min_interval=0), 199067, 2026, log=lambda *_: None)
        with db.connect() as con:      # نفس اسم الدوري الحقيقي، مع اختلاف كتابة الدولة (شرطة بدل مسافة)
            con.execute("UPDATE matches SET status='played', hg=1, ag=0 WHERE league='233' AND status!='played'")      # أرشيف حقيقي: لا مباريات قادمة
            con.execute("UPDATE leagues SET name='Premier League (Saudi-Arabia)' WHERE code='233'")
            con.execute("UPDATE leagues SET name='Premier League (Saudi Arabia)' WHERE code='hl199067'")
            db.kv_set(con, "version", "x1")

    def test_name_normalisation(self):
        self.assertEqual(service._norm_name("Pro League (Saudi-Arabia)"), service._norm_name("pro league (Saudi  Arabia)"))

    def test_archive_hidden_when_current_exists_with_same_name(self):
        self.load()
        self.assertEqual([l["code"] for l in service.leagues()], ["hl199067"])
        self.assertEqual({l["code"] for l in service.leagues(include_hidden=True)}, {"233", "hl199067"})
        self.assertEqual([l["code"] for l in api.dispatch("GET", "/api/leagues")[1]], ["hl199067"])
        hidden_team = service.list_teams(league="233")[0]["id"]                                      # الأرشيف يبقى صالحًا بالرمز المباشر
        self.assertEqual(api.dispatch("GET", "/api/teams/" + hidden_team)[0], 200)

    def test_archive_stays_visible_without_current_twin_and_current_first(self):
        importer.run(provider.Client(key="k", base=self.fb.url, min_interval=0), 233, 2024, log=lambda *_: None)
        with db.connect() as con:
            con.execute("UPDATE matches SET status='played', hg=1, ag=0 WHERE league='233' AND status!='played'"); db.kv_set(con, "version", "x0")
        self.assertEqual([l["code"] for l in service.leagues()], ["233"])
        importer.run_hl(provider.HighlightlyClient(key="hl-key", base=self.hl.url, min_interval=0), 199067, 2026, log=lambda *_: None)
        self.assertEqual([l["code"] for l in service.leagues()], ["hl199067", "233"])                  # الحالي أولًا، والأرشيف يظهر لأن اسمه مختلف

    def test_drop_league_cleans_everything_but_accounts(self):
        self.load()
        accounts_mod.register("keep2@example.com", "password123")
        hc = provider.HighlightlyClient(key="hl-key", base=self.hl.url, min_interval=0)
        importer.run_hl_stats(hc, 2, log=lambda *_: None)
        n = importer.drop_league("hl199067", log=lambda *_: None)
        self.assertEqual(n, 480)
        with db.connect() as con:
            self.assertEqual(con.execute("SELECT COUNT(*) c FROM match_stats").fetchone()["c"], 0)
            self.assertEqual(con.execute("SELECT COUNT(*) c FROM leagues WHERE code='hl199067'").fetchone()["c"], 0)
            self.assertEqual(db.kv_get(con, "hl_leagues"), "")
            self.assertTrue(all(t["id"].startswith("a") for t in [dict(r) for r in con.execute("SELECT id FROM teams")]))
        self.assertEqual([l["code"] for l in service.leagues()], ["233"])
        self.assertIsNotNone(accounts_mod.login("keep2@example.com", "password123"))
        with self.assertRaises(provider.ProviderError):
            importer.drop_league("nope", log=lambda *_: None)


class ProfessionalFeaturesTests(unittest.TestCase):
    def setUp(self):
        fresh_db()
        os.environ.pop("ADMIN_TOKEN", None)

    def test_standings_computation(self):
        import engine
        M = lambda i, d, h, a, hg, ag, season="s1": {"id": i, "date": d, "home": h, "away": a, "hg": hg, "ag": ag, "season": season, "status": "played"}
        ms = [M("1", "2026-01-01", "A", "B", 2, 0), M("2", "2026-01-08", "B", "C", 1, 0), M("3", "2026-01-15", "C", "A", 3, 1),
              M("4", "2026-01-22", "A", "C", 1, 1), M("0", "2025-01-01", "B", "A", 9, 0, season="old"),
              {"id": "5", "date": "2026-02-01", "home": "A", "away": "B", "hg": None, "ag": None, "season": "s1", "status": "scheduled"}]
        t = engine.standings(ms)
        self.assertEqual([r["team"] for r in t], ["C", "A", "B"])                           # نقاط ثم فارق أهداف
        a = next(r for r in t if r["team"] == "A")
        self.assertEqual((a["p"], a["w"], a["d"], a["l"], a["gf"], a["ga"], a["gd"], a["pts"]), (3, 1, 1, 1, 4, 4, 0, 4))
        self.assertEqual(a["form"], ["W", "L", "D"])
        self.assertEqual([r["pos"] for r in t], [1, 2, 3])                                  # الموسم القديم والمباريات غير المنتهية مستبعدة
        self.assertEqual(engine.standings([]), [])

    def test_standings_api_is_consistent(self):
        s, r = api.dispatch("GET", "/api/standings")
        self.assertEqual(s, 200); rows = r["rows"]
        self.assertEqual(len(rows), 16)
        self.assertEqual(sum(x["w"] for x in rows), sum(x["l"] for x in rows))               # كل فوز يقابله خسارة
        self.assertEqual(sum(x["gf"] for x in rows), sum(x["ga"] for x in rows))
        self.assertEqual([x["pos"] for x in rows], list(range(1, 17)))
        self.assertTrue(all(rows[i]["pts"] >= rows[i + 1]["pts"] for i in range(15)))
        self.assertEqual(api.dispatch("GET", "/api/standings", {"league": "nope"})[0], 404)

    def test_logos_stored_and_fallback_patterns(self):
        ds = build_dataset()
        fd = FakeFootballData(ds)
        try:
            importer.run_fd(provider.FootballDataClient(key="fd-key", base=fd.url, min_interval=0), "PL", log=lambda *_: None)
        finally:
            fd.close()
        teams = api.dispatch("GET", "/api/teams")[1]
        self.assertTrue(all(t["logo"].startswith("https://crests.example/") for t in teams))      # الشعار المخزَّن من المصدر
        with db.connect() as con:
            con.execute("UPDATE teams SET logo=NULL"); db.kv_set(con, "version", "n1")
        teams = api.dispatch("GET", "/api/teams")[1]
        self.assertTrue(all(t["logo"] == f"https://crests.football-data.org/{t['id'][1:]}.png" for t in teams))   # احتياطي بنمط المزوّد
        self.assertEqual(provider.default_logo("h123"), "https://highlightly.net/soccer/images/teams/123.png")
        self.assertEqual(provider.default_logo("a9"), "https://media.api-sports.io/football/teams/9.png")
        self.assertIsNone(provider.default_logo("t01")); self.assertIsNone(provider.default_logo("x"))
        m = api.dispatch("GET", "/api/matches", {"kind": "results"})[1][0]
        self.assertTrue(m["home_logo"] and m["away_logo"])
        a = api.dispatch("GET", "/api/analyze", {"home": m["home"], "away": m["away"], "match_id": m["id"]})[1]
        self.assertTrue(a["home"]["logo"] and a["away"]["logo"])
        self.assertEqual((a["match"]["status"], a["match"]["hg"]), ("played", m["hg"]))               # نتيجة المباراة تُعرض في صفحة التحليل
        self.assertTrue(api.dispatch("GET", "/api/teams/" + m["home"])[1]["team"]["logo"])
        self.assertIsNotNone(api.dispatch("GET", "/api/meta")[1]["updated_at"])

    def test_demo_has_no_logos_and_no_updated_stamp(self):
        t = api.dispatch("GET", "/api/teams")[1][0]
        self.assertIsNone(t["logo"])
        self.assertIsNone(api.dispatch("GET", "/api/meta")[1]["updated_at"])

    def test_follow_teams_flow(self):
        r = api.dispatch("POST", "/api/auth/register", body={"email": "f@example.com", "password": "password123"})[1]
        h = {"Authorization": "Bearer " + r["token"]}
        self.assertEqual(api.dispatch("GET", "/api/fav-teams")[0], 401)
        self.assertEqual(api.dispatch("POST", "/api/fav-teams", headers=h, body={"team": "t01"})[1], ["t01"])
        self.assertEqual(api.dispatch("POST", "/api/fav-teams", headers=h, body={"team": "t01"})[1], ["t01"])           # بلا تكرار
        self.assertEqual(api.dispatch("POST", "/api/fav-teams", headers=h, body={"team": "zzz"})[1]["error"]["code"], "unknown_team")
        s, sync = api.dispatch("POST", "/api/sync", headers=h, body={"favorites": [], "history": [], "teams": ["t02", "bad", "t01"]})
        self.assertEqual(sorted(sync["teams"]), ["t01", "t02"])
        self.assertEqual(api.dispatch("DELETE", "/api/fav-teams", {"team": "t01"}, h)[1], ["t02"])
        self.assertEqual(api.dispatch("POST", "/api/auth/delete", headers=h, body={"password": "password123"})[0], 200)
        with db.connect() as con:
            self.assertEqual(con.execute("SELECT COUNT(*) c FROM fav_teams").fetchone()["c"], 0)           # الحذف يشمل الفرق المتابَعة

    def test_leagues_alphabetical(self):
        ds = build_dataset()
        hl, fb = FakeHighlightly(ds), FakeFootballApi(ds)
        try:
            importer.run(provider.Client(key="k", base=fb.url, min_interval=0), 233, 2024, log=lambda *_: None)            # "Test League (Egypt)"
            importer.run_hl(provider.HighlightlyClient(key="hl-key", base=hl.url, min_interval=0), 199067, 2026, log=lambda *_: None)   # "Premier League (Egypt)"
        finally:
            hl.close(); fb.close()
        names = [l["name"] for l in service.leagues()]
        self.assertEqual(names, sorted(names, key=str.lower))
        self.assertEqual(names[0], "Premier League (Egypt)")

    def test_old_database_gets_logo_column(self):
        import sqlite3
        path = os.environ["SMM_DB"]
        con = sqlite3.connect(path)
        con.executescript("CREATE TABLE teams (id TEXT PRIMARY KEY, name TEXT NOT NULL, source TEXT NOT NULL); INSERT INTO teams VALUES ('h5','Old','x');")
        con.commit(); con.close()
        with db.connect() as c2:
            cols = [r["name"] for r in c2.execute("PRAGMA table_info(teams)")]
            self.assertIn("logo", cols)
            self.assertEqual(c2.execute("SELECT name FROM teams").fetchone()["name"], "Old")                 # البيانات القديمة محفوظة


class LiveHttpTests(unittest.TestCase):
    """يشغّل server_lite.py على منفذ حقيقي ويرسل إليه طلبات HTTP فعلية."""

    @classmethod
    def setUpClass(cls):
        fresh_db()
        os.environ["ADMIN_TOKEN"] = "live-admin"
        import server_lite
        cls.srv = server_lite.ThreadingHTTPServer(("127.0.0.1", 0), server_lite.Handler)
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        os.environ.pop("ADMIN_TOKEN", None)

    def req(self, method, path, body=None, headers=None, raw=None):
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        r = urllib.request.Request(self.base + path, data=data, method=method, headers=headers or {})
        try:
            with urllib.request.urlopen(r) as resp:
                return resp.status, resp.read(), dict(resp.headers)
        except urllib.error.HTTPError as e:
            return e.code, e.read(), dict(e.headers)

    def test_end_to_end(self):
        s, b, h = self.req("GET", "/api/health")
        self.assertEqual((s, json.loads(b)["status"]), (200, "ok"))
        self.assertEqual(h["Cache-Control"], "no-store")
        s, b, _ = self.req("GET", "/api/analyze?home=t01&away=t02&n=7")
        self.assertEqual(len(json.loads(b)["form"]["home"]), 7)
        s, b, _ = self.req("GET", "/api/analyze?home=t01&away=t01")
        self.assertEqual((s, json.loads(b)["error"]["code"]), (400, "same_team"))
        s, b, _ = self.req("POST", "/api/auth/register", {"email": "live@example.com", "password": "password123"})
        tok = json.loads(b)["token"]
        auth = {"Authorization": "Bearer " + tok, "Content-Type": "application/json"}
        s, b, _ = self.req("POST", "/api/favorites", {"home": "t01", "away": "t02"}, auth)
        self.assertEqual(json.loads(b), [{"home": "t01", "away": "t02"}])
        s, b, _ = self.req("GET", "/api/me")
        self.assertEqual(s, 401)
        s, b, _ = self.req("POST", "/api/auth/login", raw=b"{bad json")
        self.assertEqual((s, json.loads(b)["error"]["code"]), (400, "invalid_body"))
        s, b, _ = self.req("POST", "/api/auth/login", raw=b"x" * 70000)
        self.assertEqual(s, 413)
        s, b, _ = self.req("GET", "/api/admin/summary", headers={"X-Admin-Token": "live-admin"})
        self.assertEqual(s, 200); self.assertEqual(json.loads(b)["database"]["users"], 1)
        self.assertEqual(self.req("GET", "/api/admin/summary", headers={"X-Admin-Token": "no"})[0], 403)

    def test_static_files_and_traversal(self):
        s, b, h = self.req("GET", "/")
        self.assertEqual(s, 200); self.assertIn(b'dir="rtl"', b)
        self.assertEqual(self.req("GET", "/app.js")[0], 200)
        self.assertEqual(self.req("GET", "/manifest.webmanifest")[2]["Content-Type"].split(";")[0], "application/manifest+json")
        self.assertEqual(self.req("GET", "/../backend/db.py")[0], 404)
        self.assertEqual(self.req("GET", "/%2e%2e/backend/db.py")[0], 404)
        self.assertEqual(self.req("GET", "/nope.txt")[0], 404)


if __name__ == "__main__":
    unittest.main()
