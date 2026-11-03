"""الحسابات: تسجيل وتسجيل دخول وجلسات، بدون أي مكتبة خارجية.

- كلمات المرور: PBKDF2-SHA256 مع ملح عشوائي لكل مستخدم (لا تُخزَّن نصًا).
- الجلسات: رمز عشوائي يُعاد للمستخدم مرة واحدة، ويُخزَّن منه تجزئة SHA-256 فقط.
- حماية من التخمين: 5 محاولات فاشلة خلال 15 دقيقة لنفس البريد تُقفل الدخول مؤقتًا.
"""
import hashlib
import hmac
import os
import re
import secrets
from datetime import datetime, timedelta, timezone

import db

SESSION_DAYS = 30
MAX_FAILS, WINDOW_MIN = 5, 15
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[^@\s]{2,}$")


class AuthError(Exception):
    def __init__(self, status, code):
        super().__init__(code)
        self.status, self.code = status, code


def _now():
    return datetime.now(timezone.utc)


def _iso(d):
    return d.isoformat(timespec="seconds")


def _hash_pw(password, salt=None, iters=None):
    salt = salt or secrets.token_bytes(16)
    iters = iters or int(os.environ.get("SMM_PBKDF2_ITER", "600000"))
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iters)
    return f"pbkdf2${iters}${salt.hex()}${dk.hex()}"


def _verify_pw(password, stored):
    try:
        _, iters, salt, dk = stored.split("$")
        test = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), int(iters))
        return hmac.compare_digest(test.hex(), dk)
    except Exception:
        return False


def _tok_hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _new_session(con, user_id):
    token = secrets.token_urlsafe(32)
    con.execute("INSERT INTO sessions(token_hash, user_id, expires) VALUES(?,?,?)",
                (_tok_hash(token), user_id, _iso(_now() + timedelta(days=SESSION_DAYS))))
    return token


def register(email, password):
    email = (email or "").strip().lower()
    if not EMAIL_RE.match(email):
        raise AuthError(400, "invalid_email")
    if not isinstance(password, str) or len(password) < 8 or len(password) > 200:
        raise AuthError(400, "weak_password")
    with db.connect() as con:
        if con.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
            raise AuthError(409, "email_taken")
        cur = con.execute("INSERT INTO users(email, pw_hash, created) VALUES(?,?,?)",
                          (email, _hash_pw(password), _iso(_now())))
        return {"token": _new_session(con, cur.lastrowid), "user": {"id": cur.lastrowid, "email": email}}


def login(email, password):
    email = (email or "").strip().lower()
    with db.connect() as con:
        since = _iso(_now() - timedelta(minutes=WINDOW_MIN))
        fails = con.execute("SELECT COUNT(*) c FROM login_attempts WHERE email=? AND ok=0 AND at>?", (email, since)).fetchone()["c"]
        if fails >= MAX_FAILS:
            raise AuthError(429, "too_many_attempts")
        u = con.execute("SELECT id, pw_hash FROM users WHERE email=?", (email,)).fetchone()
        ok = bool(u) and isinstance(password, str) and _verify_pw(password, u["pw_hash"])
        if not u:
            _hash_pw("dummy-password")      # يحافظ على زمن استجابة متقارب
        con.execute("INSERT INTO login_attempts(email, at, ok) VALUES(?,?,?)", (email, _iso(_now()), 1 if ok else 0))
        if not ok:
            con.commit()
            raise AuthError(401, "bad_credentials")
        return {"token": _new_session(con, u["id"]), "user": {"id": u["id"], "email": email}}


def user_from_token(token):
    if not token:
        return None
    with db.connect() as con:
        r = con.execute("SELECT u.id, u.email, s.expires FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=?",
                        (_tok_hash(token),)).fetchone()
        if not r or r["expires"] < _iso(_now()):
            return None
        return {"id": r["id"], "email": r["email"]}


def logout(token):
    with db.connect() as con:
        con.execute("DELETE FROM sessions WHERE token_hash=?", (_tok_hash(token or ""),))


# ----- المفضلة والسجل -----

def fav_list(uid):
    with db.connect() as con:
        return [{"home": r["home"], "away": r["away"]} for r in
                con.execute("SELECT home, away FROM favorites WHERE user_id=? ORDER BY created DESC", (uid,))]


def fav_add(uid, home, away):
    with db.connect() as con:
        con.execute("INSERT OR IGNORE INTO favorites(user_id, home, away, created) VALUES(?,?,?,?)", (uid, home, away, _iso(_now())))


def fav_remove(uid, home, away):
    with db.connect() as con:
        con.execute("DELETE FROM favorites WHERE user_id=? AND home=? AND away=?", (uid, home, away))


def hist_list(uid, limit=30):
    with db.connect() as con:
        return [{"home": r["home"], "away": r["away"], "p": [r["p_home"], r["p_draw"], r["p_away"]], "t": r["at"][:10]} for r in
                con.execute("SELECT * FROM history WHERE user_id=? ORDER BY at DESC LIMIT ?", (uid, limit))]


def hist_add(uid, home, away, p):
    with db.connect() as con:
        con.execute("INSERT INTO history(user_id, home, away, p_home, p_draw, p_away, at) VALUES(?,?,?,?,?,?,?) "
                    "ON CONFLICT(user_id, home, away) DO UPDATE SET p_home=excluded.p_home, p_draw=excluded.p_draw, "
                    "p_away=excluded.p_away, at=excluded.at", (uid, home, away, p[0], p[1], p[2], _iso(_now())))
        con.execute("DELETE FROM history WHERE user_id=? AND rowid NOT IN "
                    "(SELECT rowid FROM history WHERE user_id=? ORDER BY at DESC LIMIT 100)", (uid, uid))


def delete_account(uid, password):
    """يحذف الحساب نهائيًا مع المفضلة والسجل والجلسات (تتطلب كلمة المرور)."""
    with db.connect() as con:
        u = con.execute("SELECT pw_hash FROM users WHERE id=?", (uid,)).fetchone()
        if not u or not isinstance(password, str) or not _verify_pw(password, u["pw_hash"]):
            raise AuthError(401, "bad_credentials")
        con.execute("DELETE FROM users WHERE id=?", (uid,))      # ON DELETE CASCADE يحذف المفضلة والسجل والجلسات


def team_follow_list(uid):
    with db.connect() as con:
        return [r["team_id"] for r in con.execute("SELECT team_id FROM fav_teams WHERE user_id=? ORDER BY created DESC", (uid,))]


def team_follow_add(uid, team_id):
    with db.connect() as con:
        con.execute("INSERT OR IGNORE INTO fav_teams(user_id, team_id, created) VALUES(?,?,?)", (uid, team_id, _iso(_now())))


def team_follow_remove(uid, team_id):
    with db.connect() as con:
        con.execute("DELETE FROM fav_teams WHERE user_id=? AND team_id=?", (uid, team_id))
