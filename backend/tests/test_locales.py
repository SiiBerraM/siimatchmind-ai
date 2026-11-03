"""اختبارات الترجمة: تطابق المفاتيح والمتغيرات {x} بين كل اللغات، وكل مفتاح يستعمله app.js موجود."""
import json
import os
import re
import unittest

FRONT = os.path.join(os.path.dirname(__file__), "..", "..", "frontend")


def load(code):
    with open(os.path.join(FRONT, "locales", code + ".json"), encoding="utf-8") as f:
        return json.load(f)


class LocaleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.langs = json.load(open(os.path.join(FRONT, "locales", "languages.json"), encoding="utf-8"))
        cls.en = load("en")

    def test_all_languages_have_same_keys_and_placeholders(self):
        for l in self.langs:
            d = load(l["code"])
            self.assertEqual(set(d), set(self.en), f"مفاتيح مختلفة في {l['code']}")
            for k, v in self.en.items():
                self.assertEqual(sorted(re.findall(r"\{(\w+)\}", v)), sorted(re.findall(r"\{(\w+)\}", d[k])), f"{l['code']}:{k}")
                self.assertTrue(d[k].strip(), f"{l['code']}:{k} فارغ")

    def test_dir_values(self):
        for l in self.langs:
            self.assertIn(l["dir"], ("rtl", "ltr"))

    def test_keys_used_in_code_exist(self):
        src = open(os.path.join(FRONT, "app.js"), encoding="utf-8").read()
        used = set(re.findall(r'\bt\("([\w.]+)"[,)]', src))
        missing = [k for k in used if k not in self.en and not k.endswith(".")]
        self.assertEqual(missing, [])
        # المفاتيح الديناميكية: رموز يعيدها الخادم
        for k in ("level.low", "level.mid", "level.good", "res.W", "res.D", "res.L", "home.today", "home.upcoming", "home.results",
                  "nav.home", "nav.analyze", "nav.teams", "nav.saved", "nav.quality"):
            self.assertIn(k, self.en)
        for code in ("few_matches", "close_probs"):
            self.assertIn("conf." + code, self.en)
        for code in ("strength", "home_adv", "home_form", "away_form", "h2h"):
            self.assertIn("reason." + code, self.en)
        for code in ("no_injury_model", "no_stats", "few_h2h", "no_availability"):
            self.assertIn("missing." + code, self.en)
        for code in ("invalid_email", "weak_password", "email_taken", "bad_credentials", "too_many_attempts", "auth_required", "invalid_param",
                     "same_team", "unknown_team", "not_found", "invalid_body", "too_large", "admin_disabled", "forbidden", "generic", "bad_kind"):
            self.assertIn("err." + code, self.en)

    def test_backend_codes_are_all_translated(self):
        # كل رمز في المحرك له ترجمة
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        import engine
        from demo_data import build_dataset
        a = engine.build_analysis(build_dataset(), "t01", "t02")
        for r in a["reasons"]:
            self.assertIn("reason." + r["k"], self.en)
        for r in a["missing_data"] + a["confidence"]["reasons"]:
            self.assertIn(("missing." if r["k"] in ("no_injury_model", "no_stats", "few_h2h", "no_availability") else "conf.") + r["k"], self.en)


if __name__ == "__main__":
    unittest.main()
