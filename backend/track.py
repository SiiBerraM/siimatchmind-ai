"""Prediction ledger: log each upcoming match once, settle it after the match, score it."""
import json
import math
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import service

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "docs" / "data" / "ledger.json"
EPS = 1e-12
WINDOW_DAYS = 3


def load():
    if LEDGER.exists():
        try:
            return json.loads(LEDGER.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"version": 1, "predictions": {}, "summary": {}}


def save(led):
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(led, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def _trip(d):
    return [float(d["home"]), float(d["draw"]), float(d["away"])]


def log_upcoming(led):
    preds = led["predictions"]
    added = skipped_id = failed = 0
    limit = (date.today() + timedelta(days=WINDOW_DAYS)).isoformat()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for lg in service.leagues():
        code = lg["code"]
        for kind in ("today", "upcoming"):
            try:
                ms = service.list_matches(kind, code, None)
            except Exception:
                continue
            for m in ms:
                mid = m.get("id")
                if mid is None:
                    skipped_id += 1
                    continue
                if m.get("date") and str(m["date"])[:10] > limit:
                    continue
                key = str(mid)
                if key in preds:
                    continue
                try:
                    res = service.analyze(m["home"], m["away"], 10, match_id=mid, log=False)
                    pr = res["prediction"]
                    final = _trip(pr["raw"])
                    model = _trip(pr["model_raw"]) if pr.get("model_raw") else final
                    mb = pr.get("market_blend")
                    entry = {
                        "league": code, "home": m["home"], "away": m["away"],
                        "date": m.get("date"), "status_at_log": kind, "logged_at": now,
                        "final": final, "model": model,
                    }
                    if mb:
                        entry["market"] = _trip(mb["market"])
                        entry["w_market"] = mb["weight"]
                    preds[key] = entry
                    added += 1
                except Exception:
                    failed += 1
    return added, skipped_id, failed


def settle(led):
    pending = {k for k, v in led["predictions"].items() if "result" not in v}
    done = 0
    if not pending:
        return 0
    for lg in service.leagues():
        try:
            ms = service._league_ds(lg["code"])["matches"]
        except Exception:
            continue
        for x in ms:
            key = str(x.get("id"))
            if key in pending and x.get("status") == "played" and x.get("hg") is not None and x.get("ag") is not None:
                o = 0 if x["hg"] > x["ag"] else (1 if x["hg"] == x["ag"] else 2)
                led["predictions"][key]["result"] = {"hg": x["hg"], "ag": x["ag"], "outcome": o}
                pending.discard(key)
                done += 1
    return done


def _score(rows, field):
    n = len(rows)
    if not n:
        return None
    b = ll = acc = 0.0
    for r in rows:
        p, o = r[field], r["result"]["outcome"]
        b += sum((p[k] - (1 if k == o else 0)) ** 2 for k in range(3))
        ll += -math.log(max(EPS, p[o]))
        acc += max(range(3), key=lambda k: p[k]) == o
    return {"n": n, "brier": round(b / n, 4), "log_loss": round(ll / n, 4), "accuracy": round(acc / n, 4)}


def score(led):
    rows = [v for v in led["predictions"].values() if "result" in v]
    with_mkt = [v for v in rows if "market" in v]
    led["summary"] = {
        "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "logged": len(led["predictions"]), "settled": len(rows),
        "pending": len(led["predictions"]) - len(rows),
        "final_all": _score(rows, "final"),
        "model_all": _score(rows, "model"),
        "final_with_market": _score(with_mkt, "final"),
        "model_with_market": _score(with_mkt, "model"),
        "market_only": _score(with_mkt, "market"),
        "baseline_uniform": {"brier": 0.6667, "log_loss": 1.0986},
    }
    return led["summary"]


if __name__ == "__main__":
    led = load()
    a, s, f = log_upcoming(led)
    d = settle(led)
    sm = score(led)
    save(led)
    wm = sum("market" in v for v in led["predictions"].values())
    print("added", a, "no_id", s, "failed", f, "settled_now", d, "with_market", wm, "of", len(led["predictions"]))
    print(json.dumps(sm, ensure_ascii=False))
