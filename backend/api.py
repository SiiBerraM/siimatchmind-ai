"""موجِّه الـ API المحايد (بدون FastAPI): كل منطق الطلبات والتحقق والأخطاء والصلاحيات هنا.

dispatch(method, path, query, headers, body) -> (status, json_obj)
يستعمله main.py (FastAPI) وserver_lite.py (خادم المكتبة القياسية)، وكلاهما محوّل رفيع فوق هذه الدالة.
الأخطاء تُعاد كرموز: {"error": {"code": "...", "params": {...}}} لتترجمها الواجهة.
"""
import hmac
import os
import re
import time
from collections import defaultdict, deque
from datetime import date

import accounts
import db
import monitor
import service

ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
VERSION = "0.8.0"

# حدّ الطلبات لكل عنوان IP (في الذاكرة): عام وللحسابات
LIMIT_GENERAL = (300, 60)      # 300 طلبًا كل 60 ثانية
LIMIT_AUTH = (10, 60)          # 10 محاولات تسجيل/دخول/حذف كل 60 ثانية
_hits = defaultdict(deque)


def _reset_limits():
    _hits.clear()


def _client_ip(headers):
    h = {k.lower(): v for k, v in headers.items()}
    peer = h.get("x-smm-peer", "")
    if peer in ("127.0.0.1", "::1", "localhost", ""):          # وراء النفق/الوكيل المحلي: نثق بترويسة Cloudflare
        fwd = h.get("cf-connecting-ip") or (h.get("x-forwarded-for", "").split(",")[0].strip())
        return fwd or peer or "local"
    return peer


def _throttle(ip, bucket, limit):
    n, win = limit
    now = time.monotonic()
    q = _hits[(ip, bucket)]
    while q and now - q[0] > win:
        q.popleft()
    if len(q) >= n:
        raise ApiError(429, "rate_limited")
    q.append(now)
    if len(_hits) > 5000:                                       # تنظيف دوري لمنع تضخم الذاكرة
        for k in [k for k, v in _hits.items() if not v or now - v[-1] > win]:
            _hits.pop(k, None)


class ApiError(Exception):
    def __init__(self, status, code, **params):
        super().__init__(code)
        self.status, self.code, self.params = status, code, params


def _id(v, name="id"):
    if not isinstance(v, str) or not ID_RE.match(v):
        raise ApiError(422, "invalid_param", name=name)
    return v


def _bearer(headers):
    h = {k.lower(): v for k, v in headers.items()}
    a = h.get("authorization", "")
    return a[7:].strip() if a.lower().startswith("bearer ") else None


def _user(headers, required=False):
    u = accounts.user_from_token(_bearer(headers))
    if required and not u:
        raise ApiError(401, "auth_required")
    return u


def _admin(headers):
    expected = os.environ.get("ADMIN_TOKEN", "")
    if not expected:
        raise ApiError(503, "admin_disabled")
    got = {k.lower(): v for k, v in headers.items()}.get("x-admin-token", "")
    if not hmac.compare_digest(got.encode(), expected.encode()):
        raise ApiError(403, "forbidden")


def _body(body, *keys):
    if not isinstance(body, dict):
        raise ApiError(400, "invalid_body")
    return [body.get(k) for k in keys]


def _league(q):
    v = q.get("league")
    if v is None:
        return None
    return _id(v, "league")


def _check_pair(ds_ids, home, away):
    if home not in ds_ids or away not in ds_ids:
        raise ApiError(404, "unknown_team")
    if home == away:
        raise ApiError(400, "same_team")


def _admin_summary():
    with db.connect() as con:
        c = lambda t: con.execute(f"SELECT COUNT(*) c FROM {t}").fetchone()["c"]
        info = {
            "users": c("users"), "favorites": c("favorites"), "history": c("history"), "predictions_logged": c("predictions"),
            "teams_in_db": c("teams"), "matches_in_db": c("matches"), "match_stats": c("match_stats"),
            "last_import": db.kv_get(con, "imported_at"), "requests_remaining": db.kv_get(con, "requests_remaining"),
            "league": db.kv_get(con, "league"), "season": db.kv_get(con, "season"),
            "last_refresh": db.kv_get(con, "last_refresh"), "refresh_error": db.kv_get(con, "refresh_error") or None,
            "last_refresh_hl": db.kv_get(con, "last_refresh_hl"), "refresh_error_hl": db.kv_get(con, "refresh_error_hl") or None,
        }
    q = service.quality()
    return {"database": info, "dataset": service.meta(), "live_quality": monitor.evaluate(),
            "backtest": {k: q.get(k) for k in ("available", "tested_matches", "model", "baseline", "calibration_error")}}


def dispatch(method, path, query=None, headers=None, body=None):
    query, headers = query or {}, headers or {}
    try:
        ip = _client_ip(headers)
        if path.startswith("/api/"):
            _throttle(ip, "general", LIMIT_GENERAL)
            if path.startswith("/api/auth/"):
                _throttle(ip, "auth", LIMIT_AUTH)
        return 200, _route(method.upper(), path.rstrip("/") or "/", query, headers, body)
    except ApiError as e:
        return e.status, {"error": {"code": e.code, "params": e.params}}
    except accounts.AuthError as e:
        return e.status, {"error": {"code": e.code, "params": {}}}
    except KeyError as e:
        code = "unknown_league" if e.args and e.args[0] == "unknown_league" else "not_found"
        return 404, {"error": {"code": code, "params": {}}}
    except ValueError as e:
        return 400, {"error": {"code": str(e) or "bad_request", "params": {}}}


def _route(method, path, q, headers, body):
    if path == "/api/health" and method == "GET":
        return {"status": "ok", "app": "SiiMatchMind AI", "version": VERSION}
    if path == "/api/meta" and method == "GET":
        return service.meta()
    if path == "/api/teams" and method == "GET":
        s = q.get("q")
        if s is not None and len(s) > 40:
            raise ApiError(422, "invalid_param", name="q")
        return service.list_teams(s, _league(q))
    m = re.match(r"^/api/teams/([^/]+)$", path)
    if m and method == "GET":
        return service.team_detail(_id(m.group(1)))
    if path == "/api/matches" and method == "GET":
        k = q.get("kind", "today")
        if k not in ("today", "upcoming", "results"):
            raise ApiError(422, "invalid_param", name="kind")
        return service.list_matches(k, _league(q))
    if path == "/api/analyze" and method == "GET":
        home, away = _id(q.get("home"), "home"), _id(q.get("away"), "away")
        try:
            n = int(q.get("n", 10))
        except ValueError:
            raise ApiError(422, "invalid_param", name="n")
        if not 5 <= n <= 10:
            raise ApiError(422, "invalid_param", name="n")
        mid = q.get("match_id")
        if mid is not None:
            _id(mid, "match_id")
        _check_pair({t["id"] for t in service.dataset()["teams"]}, home, away)
        res = service.analyze(home, away, n, match_id=mid)
        u = _user(headers)
        if u:
            p = res["prediction"]["percent"]
            accounts.hist_add(u["id"], home, away, [p["home"], p["draw"], p["away"]])
        return res
    if path == "/api/quality" and method == "GET":
        return service.quality(_league(q))
    if path == "/api/leagues" and method == "GET":
        return service.leagues()
    if path == "/api/standings" and method == "GET":
        return service.standings_table(_league(q))

    # ----- الحسابات -----
    if path == "/api/auth/register" and method == "POST":
        email, pw = _body(body, "email", "password")
        return accounts.register(email, pw)
    if path == "/api/auth/login" and method == "POST":
        email, pw = _body(body, "email", "password")
        return accounts.login(email, pw)
    if path == "/api/auth/delete" and method == "POST":
        u = _user(headers, required=True)
        (pw,) = _body(body, "password")
        accounts.delete_account(u["id"], pw)
        return {"ok": True}
    if path == "/api/auth/logout" and method == "POST":
        accounts.logout(_bearer(headers))
        return {"ok": True}
    if path == "/api/me" and method == "GET":
        return {"user": _user(headers, required=True)}
    if path == "/api/favorites":
        u = _user(headers, required=True)
        ids = {t["id"] for t in service.dataset()["teams"]}
        if method == "GET":
            return accounts.fav_list(u["id"])
        if method == "POST":
            home, away = _body(body, "home", "away")
            _check_pair(ids, _id(home, "home"), _id(away, "away"))
            accounts.fav_add(u["id"], home, away)
            return accounts.fav_list(u["id"])
        if method == "DELETE":
            home, away = _id(q.get("home"), "home"), _id(q.get("away"), "away")
            accounts.fav_remove(u["id"], home, away)
            return accounts.fav_list(u["id"])
    if path == "/api/fav-teams":
        u = _user(headers, required=True)
        ids = {t["id"] for t in service.dataset()["teams"]}
        if method == "GET":
            return accounts.team_follow_list(u["id"])
        if method == "POST":
            (tid,) = _body(body, "team")
            if _id(tid, "team") not in ids:
                raise ApiError(404, "unknown_team")
            accounts.team_follow_add(u["id"], tid)
            return accounts.team_follow_list(u["id"])
        if method == "DELETE":
            accounts.team_follow_remove(u["id"], _id(q.get("team"), "team"))
            return accounts.team_follow_list(u["id"])
    if path == "/api/history" and method == "GET":
        return accounts.hist_list(_user(headers, required=True)["id"])
    if path == "/api/sync" and method == "POST":
        u = _user(headers, required=True)
        favs, hist = _body(body, "favorites", "history")
        for tid in (body.get("teams") or [])[:100] if isinstance(body, dict) else []:
            if isinstance(tid, str) and tid in {t["id"] for t in service.dataset()["teams"]}:
                accounts.team_follow_add(u["id"], tid)
        ids = {t["id"] for t in service.dataset()["teams"]}
        for f in (favs or [])[:100]:
            if isinstance(f, dict) and f.get("home") in ids and f.get("away") in ids and f["home"] != f["away"]:
                accounts.fav_add(u["id"], f["home"], f["away"])
        for h in (hist or [])[:100]:
            if isinstance(h, dict) and h.get("home") in ids and h.get("away") in ids and isinstance(h.get("p"), list) \
                    and len(h["p"]) == 3 and all(isinstance(x, int) for x in h["p"]):
                accounts.hist_add(u["id"], h["home"], h["away"], h["p"])
        return {"favorites": accounts.fav_list(u["id"]), "history": accounts.hist_list(u["id"]), "teams": accounts.team_follow_list(u["id"])}

    # ----- الإدارة (برمز ADMIN_TOKEN من متغيرات البيئة) -----
    if path == "/api/admin/summary" and method == "GET":
        _admin(headers)
        return _admin_summary()
    raise ApiError(404, "not_found") if path.startswith("/api/") else KeyError(path)
