import sys

def edit(path, fn):
    s = open(path, encoding="utf-8").read()
    t = fn(s)
    open(path, "w", encoding="utf-8").write(t)
    compile(t, path, "exec")
    print(path, "patched")

# ---------- db.py: جدول المديرين ----------
def db_py(s):
    if "CREATE TABLE IF NOT EXISTS admins" in s:
        return s
    key = "CREATE TABLE IF NOT EXISTS users (\n  id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT NOT NULL UNIQUE, pw_hash TEXT NOT NULL, created TEXT NOT NULL);\n"
    assert s.count(key) == 1, "users table block not found exactly once"
    add = "CREATE TABLE IF NOT EXISTS admins (\n  user_id INTEGER PRIMARY KEY, name TEXT NOT NULL, FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE);\n"
    return s.replace(key, key + add)

# ---------- accounts.py: دوال المدير ----------
def accounts_py(s):
    if "def make_admin" in s:
        return s
    return s.rstrip("\n") + '''


# ---------- حساب المدير ----------
def is_admin(uid):
    with db.connect() as con:
        return con.execute("SELECT 1 FROM admins WHERE user_id=?", (uid,)).fetchone() is not None


def admin_info(uid):
    with db.connect() as con:
        r = con.execute("SELECT name FROM admins WHERE user_id=?", (uid,)).fetchone()
    return {"admin": True, "name": r["name"]} if r else {"admin": False}


def make_admin(email, password, name="Berra"):
    """ينشئ الحساب أو يحدّث كلمة سره، ويجعله مديرًا. يُستدعى من make_admin.py فقط (لا من الشبكة)."""
    email = (email or "").strip().lower()
    if "@" not in email or len(password or "") < 10:
        raise ValueError("invalid_admin_input")
    with db.connect() as con:
        r = con.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
        if r:
            uid = r["id"]
            con.execute("UPDATE users SET pw_hash=? WHERE id=?", (_hash_pw(password), uid))
        else:
            cur = con.execute("INSERT INTO users(email, pw_hash, created) VALUES(?,?,?)", (email, _hash_pw(password), _iso(_now())))
            uid = cur.lastrowid
        con.execute("INSERT OR REPLACE INTO admins(user_id, name) VALUES(?,?)", (uid, name))
        con.execute("DELETE FROM sessions WHERE user_id=?", (uid,))
    return uid
'''

# ---------- api.py: صلاحية المدير + /api/me ----------
OLD_ADMIN = '''def _admin(headers):
    expected = os.environ.get("ADMIN_TOKEN", "")
    if not expected:
        raise ApiError(503, "admin_disabled")
    got = {k.lower(): v for k, v in headers.items()}.get("x-admin-token", "")
    if not hmac.compare_digest(got.encode(), expected.encode()):
        raise ApiError(403, "forbidden")
'''
NEW_ADMIN = '''def _admin(headers):
    """يقبل جلسة حساب مدير (مثل Berra) أو الرمز السري ADMIN_TOKEN."""
    try:
        u = _user(headers, required=False)
    except ApiError:
        u = None
    if u and accounts.is_admin(u["id"]):
        return
    expected = os.environ.get("ADMIN_TOKEN", "")
    if not expected:
        raise ApiError(503, "admin_disabled")
    got = {k.lower(): v for k, v in headers.items()}.get("x-admin-token", "")
    if not hmac.compare_digest(got.encode(), expected.encode()):
        raise ApiError(403, "forbidden")
'''
OLD_ME = '        return {"user": _user(headers, required=True)}'
NEW_ME = '        u = _user(headers, required=True)\n        return {"user": {**u, **accounts.admin_info(u["id"])}}'

def api_py(s):
    if "accounts.is_admin" in s:
        return s
    assert s.count(OLD_ADMIN) == 1, "_admin function not found exactly once"
    assert s.count(OLD_ME) == 1, "/api/me return line not found exactly once"
    return s.replace(OLD_ADMIN, NEW_ADMIN).replace(OLD_ME, NEW_ME)

edit("db.py", db_py)
edit("accounts.py", accounts_py)
edit("api.py", api_py)
print("DONE")
