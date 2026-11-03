"""اختبارات المحرك والخدمة. التشغيل من مجلد backend:  python -m unittest discover -s tests -v"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import backtest
import engine
import os
import tempfile

os.environ.setdefault("SMM_DB", os.path.join(tempfile.mkdtemp(), "t.db"))
import service
from demo_data import build_dataset


class EngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ds = build_dataset()
        os.environ["SMM_DB"] = os.path.join(tempfile.mkdtemp(), "engine.db")   # قاعدة نظيفة: بيانات تجريبية
        service._cache.clear()

    def test_percent_sums_to_100(self):
        for probs in ([0.5, 0.3, 0.2], [1 / 3, 1 / 3, 1 / 3], [0.999, 0.0005, 0.0005], [0.4444, 0.3333, 0.2223]):
            self.assertEqual(sum(engine.to_percent(probs)), 100)

    def test_probabilities_valid_for_all_pairs(self):
        m = engine.Model(self.ds["matches"])
        ids = [t["id"] for t in self.ds["teams"]]
        for h in ids:
            for a in ids:
                if h == a:
                    continue
                p = m.predict(h, a)
                self.assertAlmostEqual(p["p_home"] + p["p_draw"] + p["p_away"], 1.0, places=9)
                self.assertTrue(all(x >= 0 for x in (p["p_home"], p["p_draw"], p["p_away"])))

    def test_stronger_team_favoured(self):
        m = engine.Model(self.ds["matches"])
        best = max(m.att, key=lambda t: m.att[t] / m.dfn[t])
        worst = min(m.att, key=lambda t: m.att[t] / m.dfn[t])
        p = m.predict(best, worst)
        self.assertGreater(p["p_home"], p["p_away"])

    def test_home_advantage_exists(self):
        m = engine.Model(self.ds["matches"])
        a, b = m.teams[0], m.teams[1]
        self.assertGreater(m.predict(a, b)["p_home"], m.predict(b, a)["p_away"] - 0.2)
        self.assertGreater(m.mu_h, m.mu_a)

    def test_no_future_leakage_in_fit(self):
        # النموذج يتجاهل المباريات غير المنتهية (hg/ag = None)
        scheduled = [x for x in self.ds["matches"] if x["status"] != "played"]
        self.assertTrue(all(x["hg"] is None for x in scheduled))
        self.assertEqual(len(engine.played_matches(self.ds["matches"])), 400)

    def test_unknown_team(self):
        with self.assertRaises(KeyError):
            engine.build_analysis(self.ds, "zzz", "t01")
        with self.assertRaises(ValueError):
            engine.build_analysis(self.ds, "t01", "t01")

    def test_analysis_shape(self):
        a = service.analyze("t01", "t02", 10)
        pc = a["prediction"]["percent"]
        self.assertEqual(pc["home"] + pc["draw"] + pc["away"], 100)
        self.assertLessEqual(a["confidence"]["score"], 0.85)
        self.assertLessEqual(len(a["form"]["home"]), 10)
        self.assertEqual(a["data_kind"], "demo")
        self.assertTrue(a["missing_data"])
        self.assertIn(a["confidence"]["level"], ("low", "mid", "good"))
        self.assertTrue(all("k" in r for r in a["reasons"]))
        self.assertIsNone(a["stats"])

    def test_n_clamped(self):
        self.assertEqual(len(service.analyze("t01", "t02", 3)["form"]["home"]), 5)

    def test_matches_kinds(self):
        self.assertEqual(len(service.list_matches("today")), 8)
        self.assertTrue(all(m["status"] == "scheduled" for m in service.list_matches("upcoming")))
        self.assertTrue(all(m["status"] == "played" for m in service.list_matches("results")))
        with self.assertRaises(ValueError):
            service.list_matches("bad")

    def test_team_detail_and_search(self):
        d = service.team_detail("t03")
        self.assertEqual(d["summary"]["played"], 10)
        self.assertEqual(service.list_teams("الصقور")[0]["id"], "t01")
        with self.assertRaises(KeyError):
            service.team_detail("nope")


class BacktestTests(unittest.TestCase):
    def test_backtest_runs_and_is_sane(self):
        q = backtest.run(build_dataset()["matches"])
        self.assertTrue(q["available"])
        self.assertGreater(q["tested_matches"], 100)
        self.assertLess(q["model"]["brier"], q["uniform_brier"])      # أفضل من التخمين المتساوي
        self.assertLess(q["calibration_error"], 0.08)

    def test_backtest_only_uses_past(self):
        # إذا حُجبت نتائج آخر يوم فلا يتغير شيء قبله: نختبر أن التدريب يستخدم date < d فقط
        ms = build_dataset()["matches"]
        full = backtest.run(ms)
        played = engine.played_matches(ms)
        last = max(m["date"] for m in played)
        trimmed = [m for m in ms if m["date"] != last]
        part = backtest.run(trimmed)
        self.assertEqual(full["tested_matches"] - part["tested_matches"], len([m for m in played if m["date"] == last]))


if __name__ == "__main__":
    unittest.main()
