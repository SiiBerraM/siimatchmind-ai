"""اختبار دخان للخادم الشغّال (أي خادم: FastAPI أو server_lite). بدون مكتبات خارجية.

شغّل الخادم في جلسة Termux، ثم من جلسة ثانية:
    python smoke_test.py                       # يختبر http://127.0.0.1:8000
    ADMIN_TOKEN=xyz python smoke_test.py       # إن كان الخادم مشغّلًا بنفس ADMIN_TOKEN يختبر لوحة الإدارة أيضًا
"""
import json
import os
import sys
import urllib.error
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")
results = []


def call(method, path, body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    h = {"Content-Type": "application/json", **(headers or {})}
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw[:1] in (b"{", b"[") else raw)
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, raw
    except Exception as e:
        return 0, str(e)


def check(name, cond, extra=""):
    results.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name + (f"  -> {extra}" if not cond and extra else ""))


s, r = call("GET", "/api/health")
if s == 0:
    sys.exit(f"تعذّر الاتصال بالخادم على {BASE}: {r}\nتأكد أن الخادم يعمل في جلسة Termux أخرى.")
check("health", s == 200 and r.get("status") == "ok", r)
s, meta = call("GET", "/api/meta"); check("meta", s == 200 and "kind" in meta, meta)
s, teams = call("GET", "/api/teams"); check("teams", s == 200 and len(teams) >= 2, teams)
a, b = teams[0]["id"], teams[1]["id"]
s, r = call("GET", f"/api/teams/{a}"); check("team detail", s == 200 and r["team"]["id"] == a, r)
for k in ("today", "upcoming", "results"):
    s, r = call("GET", f"/api/matches?kind={k}"); check(f"matches/{k}", s == 200 and isinstance(r, list), r)
s, r = call("GET", f"/api/analyze?home={a}&away={b}")
p = r["prediction"]["percent"] if s == 200 else {}
check("analyze (sum = 100)", s == 200 and p.get("home", 0) + p.get("draw", 0) + p.get("away", 0) == 100, r)
s, r = call("GET", f"/api/analyze?home={a}&away={a}"); check("same team rejected (400)", s == 400, r)
s, r = call("GET", "/api/analyze?home=../x&away=y"); check("bad id rejected (422)", s == 422, r)
s, r = call("GET", "/api/quality"); check("quality", s == 200 and "available" in r, r)
s, r = call("GET", "/api/favorites"); check("favorites need login (401)", s == 401, r)
email = f"smoke{os.getpid()}@example.com"
s, r = call("POST", "/api/auth/register", {"email": email, "password": "password123"})
check("register", s == 200 and "token" in r, r)
if s == 200:
    h = {"Authorization": "Bearer " + r["token"]}
    s, r = call("POST", "/api/favorites", {"home": a, "away": b}, h); check("add favorite", s == 200 and len(r) == 1, r)
    s, r = call("GET", f"/api/analyze?home={a}&away={b}", None, h); check("analyze logged-in", s == 200)
    s, r = call("GET", "/api/history", None, h); check("history saved", s == 200 and len(r) == 1, r)
    s, r = call("POST", "/api/auth/logout", {}, h); check("logout", s == 200, r)
    s, r = call("GET", "/api/me", None, h); check("token invalid after logout (401)", s == 401, r)
s, r = call("POST", "/api/auth/login", {"email": email, "password": "wrong-password"}); check("wrong password (401)", s == 401, r)
s, page = call("GET", "/"); check("frontend index served", s == 200 and b"<html" in page, page[:60] if isinstance(page, bytes) else page)
tok = os.environ.get("ADMIN_TOKEN")
if tok:
    s, r = call("GET", "/api/admin/summary", None, {"X-Admin-Token": tok}); check("admin summary", s == 200 and "database" in r, r)
    s, r = call("GET", "/api/admin/summary", None, {"X-Admin-Token": "wrong"}); check("admin wrong token (403)", s == 403, r)
print(f"\n{sum(results)}/{len(results)} نجح" + ("  ✔ كل شيء سليم" if all(results) else "  ✘ هناك إخفاقات، أرسل لي المخرجات"))
sys.exit(0 if all(results) else 1)
