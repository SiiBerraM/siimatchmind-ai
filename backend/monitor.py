"""مراقبة جودة التوقعات الحية: كل توقع لمباراة قادمة يُسجَّل، وعند انتهاء المباراة يُقارَن بالنتيجة الفعلية."""
import math
from datetime import date, datetime, timezone

import db

EPS = 1e-12


def log_prediction(match_id, home, away, raw):
    with db.connect() as con:
        con.execute("INSERT OR IGNORE INTO predictions(match_id,day,home,away,p_home,p_draw,p_away,logged_at) VALUES(?,?,?,?,?,?,?,?)",
                    (match_id, date.today().isoformat(), home, away, raw["home"], raw["draw"], raw["away"],
                     datetime.now(timezone.utc).isoformat(timespec="seconds")))


def evaluate():
    """Brier وLog Loss والدقة للتوقعات التي انتهت مبارياتها. يأخذ أول توقع مسجَّل لكل مباراة (الأقدم) لتجنب الانحياز."""
    with db.connect() as con:
        total = con.execute("SELECT COUNT(*) c FROM predictions").fetchone()["c"]
        rows = con.execute(
            "SELECT p.match_id, p.p_home, p.p_draw, p.p_away, m.hg, m.ag FROM predictions p JOIN matches m ON m.id=p.match_id "
            "WHERE m.status='played' AND p.id IN (SELECT MIN(id) FROM predictions GROUP BY match_id)").fetchall()
    n = len(rows)
    out = {"logged": total, "resolved": n, "pending": total - n}
    if n:
        b = ll = acc = 0.0
        for r in rows:
            o = 0 if r["hg"] > r["ag"] else (1 if r["hg"] == r["ag"] else 2)
            p = [r["p_home"], r["p_draw"], r["p_away"]]
            b += sum((p[k] - (1 if k == o else 0)) ** 2 for k in range(3))
            ll += -math.log(max(EPS, p[o]))
            acc += max(range(3), key=lambda k: p[k]) == o
        out.update({"brier": round(b / n, 4), "log_loss": round(ll / n, 4), "accuracy": round(acc / n, 4)})
    return out
