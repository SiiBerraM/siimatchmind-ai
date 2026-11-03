"""نسخة احتياطية لقاعدة البيانات (حسابات، مفضلة، بيانات، توقعات).  الاستخدام من مجلد backend:  python backup.py
تُحفظ في data/backups/ مع الإبقاء على آخر 7 نسخ. الاستعادة: أوقف الخادم ثم انسخ الملف فوق data/smm.db.
"""
import sqlite3
from datetime import datetime
from pathlib import Path

import db

KEEP = 7


def run():
    src = Path(db.path())
    if not src.exists():
        raise SystemExit("لا توجد قاعدة بيانات بعد: " + str(src))
    out_dir = src.parent / "backups"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"smm-{datetime.now():%Y%m%d-%H%M%S}.db"
    a, b = sqlite3.connect(src), sqlite3.connect(out)
    with b:
        a.backup(b)                       # نسخ متسق حتى والخادم يعمل
    a.close(); b.close()
    old = sorted(out_dir.glob("smm-*.db"))
    for f in old[:-KEEP]:
        f.unlink()
    return out


if __name__ == "__main__":
    print("تم:", run())
