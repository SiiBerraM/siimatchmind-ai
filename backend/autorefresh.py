"""تحديث تلقائي للبيانات الحقيقية في الخلفية (football-data.org فقط).

- يعمل إن كان FOOTBALL_DATA_KEY مضبوطًا وكانت قاعدة البيانات مستوردة من football-data.
- طلب واحد لكل تحديث (ضمن حد 10/دقيقة). الفاصل الافتراضي 6 ساعات: SMM_REFRESH_HOURS (0 = تعطيل).
- لا يخلط المصادر ولا يمس الحسابات. أي خطأ يُسجَّل في قاعدة البيانات ويظهر في لوحة الإدارة ولا يوقف الخادم.
- API-Football لا يُحدَّث تلقائيًا (حصته اليومية محدودة).
"""
import os
import threading
import time
from datetime import datetime, timezone

import db
import importer
import provider

_started = False


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def refresh_once(client=None, log=lambda *_: None):
    """يعيد True إن حدث تحديث. يسجّل الأخطاء ولا يرفعها."""
    with db.connect() as con:
        comps = [c for c in (db.kv_get(con, "competitions") or db.kv_get(con, "competition") or "").split(",") if c]
    if not comps:
        return False
    errors = []
    try:
        client = client or provider.FootballDataClient()
        for comp in comps:                      # فشل بطولة لا يمنع تحديث البقية
            try:
                importer.run_fd(client, comp, None, replace=False, log=log)
            except provider.ProviderError as e:
                errors.append(f"{comp}: {e}")
    except (provider.ProviderError, UnicodeError) as e:
        errors.append(str(e))
    with db.connect() as con:
        db.kv_set(con, "refresh_error", f"{_now()} " + " | ".join(errors) if errors else "")
        if len(errors) < len(comps):
            db.kv_set(con, "last_refresh", _now())
    return len(errors) < len(comps)


def refresh_hl_once(client=None, log=lambda *_: None):
    """يحدّث دوريات Highlightly المستوردة (3–4 طلبات لكل دوري). يتوقف عند اقتراب نفاد الحصة اليومية."""
    with db.connect() as con:
        items = [c for c in (db.kv_get(con, "hl_leagues") or "").split(",") if c]
    if not items:
        return False
    errors, ok = [], 0
    try:
        client = client or provider.HighlightlyClient()
        for it in items:
            lid, season = it.split(":")
            try:
                importer.run_hl(client, int(lid), int(season), log=log)
                ok += 1
            except provider.BudgetExhausted as e:
                errors.append(str(e))
                break
            except provider.ProviderError as e:
                errors.append(f"{lid}: {e}")
        if os.environ.get("SMM_HL_EXTRAS", "1") == "1" and not errors:       # إحصائيات وتشكيلات ضمن الحصة المتبقية
            try:
                importer.run_hl_stats(client, 8, log=log)
                importer.run_hl_lineups(client, 1, log=log)
            except provider.ProviderError as e:
                errors.append(f"extras: {e}")
    except (provider.ProviderError, UnicodeError) as e:
        errors.append(str(e))
    with db.connect() as con:
        db.kv_set(con, "refresh_error_hl", f"{_now()} " + " | ".join(errors) if errors else "")
        if ok:
            db.kv_set(con, "last_refresh_hl", _now())
    return ok > 0


def _stale(hours, key="last_refresh"):
    with db.connect() as con:
        last = db.kv_get(con, key) or db.kv_get(con, "imported_at")
    if not last:
        return True
    try:
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(last)).total_seconds()
    except ValueError:
        return True
    return age >= hours * 3600


def start():
    """يشغّل خيط التحديث مرة واحدة. آمن للاستدعاء المتكرر."""
    global _started
    hours = float(os.environ.get("SMM_REFRESH_HOURS", "6"))
    hl_hours = float(os.environ.get("SMM_HL_REFRESH_HOURS", "12"))     # حصة Highlightly: 100 طلب/يوم، فالفاصل أطول
    has_fd, has_hl = bool(os.environ.get("FOOTBALL_DATA_KEY")), bool(os.environ.get("HIGHLIGHTLY_KEY"))
    if _started or not ((has_fd and hours > 0) or (has_hl and hl_hours > 0)):
        return False
    _started = True

    def loop():
        while True:
            try:
                if has_fd and hours > 0 and _stale(hours):
                    refresh_once()
                if has_hl and hl_hours > 0 and _stale(hl_hours, "last_refresh_hl"):
                    refresh_hl_once()
            except Exception as e:      # لا يموت الخيط أبدًا
                try:
                    with db.connect() as con:
                        db.kv_set(con, "refresh_error", f"{_now()} {e}")
                except Exception:
                    pass
            time.sleep(600)             # يفحص كل 10 دقائق هل حان موعد التحديث

    threading.Thread(target=loop, daemon=True, name="smm-refresh").start()
    return True
